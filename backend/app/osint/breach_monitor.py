"""
DataShield OSINT - Breach Monitoring Module
============================================
Multi-source breach checking — no paid key required for real data.

Sources (in priority order):
  1. XposedOrNot  — FREE, no key, 17B+ records, JSON API
  2. HIBP v3      — OPTIONAL paid key ($3.50/mo), 700+ breaches, most authoritative
  3. Pwned Passwords — FREE, no key, k-anonymity password check (847M passwords)

Strategy:
  - XposedOrNot runs always — gives real breach results for free.
  - HIBP runs when HIBP_API_KEY is set — adds extra coverage.
  - Results are merged and deduplicated by breach name.
  - Pwned Passwords is a separate method (password hash check).
"""
import asyncio
import hashlib
from typing import List, Dict, Any, Optional
import httpx

from app.core.config import settings


# ── Known breach metadata lookup ─────────────────────────────────────────────
# XposedOrNot free tier returns only breach names, not data classes.
# This table enriches the most common breaches so severity is meaningful.
# Format: "BreachName": {"classes": [...], "date": "YYYY-MM-DD", "count": N, "domain": "..."}
_KNOWN_BREACH_DATA: Dict[str, Dict] = {
    "Adobe":             {"classes": ["Email addresses", "Passwords", "Usernames"], "date": "2013-10-04", "count": 152445165, "domain": "adobe.com"},
    "LinkedIn":          {"classes": ["Email addresses", "Passwords"], "date": "2012-05-05", "count": 164611595, "domain": "linkedin.com"},
    "Dropbox":           {"classes": ["Email addresses", "Passwords"], "date": "2012-07-01", "count": 68648009,  "domain": "dropbox.com"},
    "MySpace":           {"classes": ["Email addresses", "Passwords", "Usernames"], "date": "2008-07-01", "count": 359420698, "domain": "myspace.com"},
    "Twitter":           {"classes": ["Email addresses", "Usernames"], "date": "2022-07-22", "count": 235000000, "domain": "twitter.com"},
    "Facebook":          {"classes": ["Email addresses", "Phone numbers", "Usernames", "Dates of birth"], "date": "2021-04-03", "count": 533000000, "domain": "facebook.com"},
    "Canva":             {"classes": ["Email addresses", "Passwords", "Usernames"], "date": "2019-05-24", "count": 137272116, "domain": "canva.com"},
    "Zynga":             {"classes": ["Email addresses", "Passwords", "Phone numbers", "Usernames"], "date": "2019-09-01", "count": 172869660, "domain": "zynga.com"},
    "Chegg":             {"classes": ["Email addresses", "Passwords", "Usernames", "Dates of birth"], "date": "2018-04-29", "count": 40000000, "domain": "chegg.com"},
    "Quora":             {"classes": ["Email addresses", "Passwords", "Usernames"], "date": "2018-12-03", "count": 100000000, "domain": "quora.com"},
    "Wattpad":           {"classes": ["Email addresses", "Passwords", "Usernames", "Dates of birth", "Physical addresses"], "date": "2020-06-29", "count": 270000000, "domain": "wattpad.com"},
    "ShareThis":         {"classes": ["Email addresses", "Passwords", "Usernames", "Dates of birth"], "date": "2018-07-01", "count": 41000000, "domain": "sharethis.com"},
    "AntiPublicCombo":   {"classes": ["Email addresses", "Passwords"], "date": "2016-12-09", "count": 457962538, "domain": ""},
    "Collection1":       {"classes": ["Email addresses", "Passwords"], "date": "2019-01-07", "count": 772904991, "domain": ""},
    "Verifications":     {"classes": ["Email addresses", "Phone numbers", "Physical addresses"], "date": "2019-02-25", "count": 763117241, "domain": ""},
    "NeimanMarcus":      {"classes": ["Credit cards", "Email addresses"], "date": "2013-12-15", "count": 1100000, "domain": "neimanmarcus.com"},
    "CarnivalCorporation":{"classes": ["Email addresses", "Physical addresses", "Phone numbers"], "date": "2019-03-01", "count": 5000000, "domain": "carnival.com"},
    "StarTribune":       {"classes": ["Email addresses", "Passwords"], "date": "2019-01-01", "count": 1000000, "domain": "startribune.com"},
    "ExploitIN":         {"classes": ["Email addresses", "Passwords"], "date": "2021-01-01", "count": 694000000, "domain": ""},
    "Alleged-SOCRadar":  {"classes": ["Email addresses"], "date": "2022-08-01", "count": 5000000, "domain": ""},
}


class BreachMonitor:
    """
    Checks multiple public breach databases for exposed email addresses.

    Free tier (no keys needed):
      - XposedOrNot: 17B+ records, REST API, no auth
      - Pwned Passwords: 847M leaked passwords, k-anonymity

    Enhanced tier (with API key):
      - HIBP v3: authoritative breach metadata, paste lookups
    """

    # ── API endpoints ────────────────────────────────────────────────────────
    XON_BASE              = "https://api.xposedornot.com/v1"
    HIBP_BASE             = "https://haveibeenpwned.com/api/v3"
    PWNED_PASSWORDS_BASE  = "https://api.pwnedpasswords.com"

    def __init__(self):
        self.hibp_key = settings.HIBP_API_KEY
        self._hibp_headers = {
            "hibp-api-key": self.hibp_key,
            "User-Agent": "DataShield-OSINT/1.0 (privacy-protection-platform)",
        }

    # ── Public interface ─────────────────────────────────────────────────────

    async def check_email_breaches(self, email: str) -> List[Dict[str, Any]]:
        """
        Check email across all configured sources.
        Always returns real results — XposedOrNot is free and needs no key.
        """
        tasks = [self._check_xon(email)]
        if self.hibp_key:
            tasks.append(self._check_hibp(email))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge and deduplicate by breach name
        merged: Dict[str, Dict] = {}
        for result in results:
            if isinstance(result, list):
                for breach in result:
                    key = breach.get("Name", "").lower()
                    if key and key not in merged:
                        merged[key] = breach
                    elif not key:
                        merged[str(id(breach))] = breach  # unnamed — keep all

        return list(merged.values())

    async def check_password_pwned(self, password: str) -> int:
        """
        Check if a password appears in public breach dumps using k-Anonymity.
        Only the first 5 chars of the SHA-1 hash are sent — password never leaves.
        Returns count of appearances (0 = not found).
        """
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{self.PWNED_PASSWORDS_BASE}/range/{prefix}",
                    headers={"User-Agent": "DataShield-OSINT/1.0"},
                )
                resp.raise_for_status()
                for line in resp.text.splitlines():
                    h, count = line.split(":")
                    if h == suffix:
                        return int(count)
                return 0
            except Exception:
                return 0

    async def get_pastes(self, email: str) -> List[Dict[str, Any]]:
        """
        Retrieve paste site mentions for an email (HIBP only — needs key).
        Returns empty list gracefully when key is not configured.
        """
        if not self.hibp_key:
            return []
        url = f"{self.HIBP_BASE}/pasteaccount/{email}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=self._hibp_headers)
                if resp.status_code == 404:
                    return []
                resp.raise_for_status()
                return resp.json()
            except Exception:
                return []

    # ── XposedOrNot (free, no key) ────────────────────────────────────────────

    async def _check_xon(self, email: str) -> List[Dict[str, Any]]:
        """
        Query XposedOrNot free API.
        Endpoint: GET /v1/check-email/{email}

        Returns empty list when email is clean (404) or API is unavailable.
        Response shape (abbreviated):
          { "breaches": [["BreachName", "2022-01-01", "email,password", 50000], ...],
            "BreachMetrics": { ... } }
        """
        url = f"{self.XON_BASE}/check-email/{email}"
        headers = {
            "User-Agent": "DataShield-OSINT/1.0 (privacy-protection-platform)",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 404:
                    return []   # clean email
                if resp.status_code == 400:
                    return []   # invalid email format
                resp.raise_for_status()

                data = resp.json()
                return self._parse_xon_response(data, email)
        except httpx.HTTPStatusError:
            return []
        except Exception:
            return []

    def _parse_xon_response(
        self, data: Dict, email: str
    ) -> List[Dict[str, Any]]:
        """
        Convert XposedOrNot response to DataShield breach format.

        XposedOrNot free API returns breach names only — a flat list inside a list:
          { "breaches": [["Adobe", "LinkedIn", "ShareThis", ...]], "status": "success" }

        The "breaches" key contains ONE element which is the list of names.
        We convert each name into a breach dict, enriching data classes from
        a known-breach lookup table so severity is meaningful.
        """
        raw = data.get("breaches", [])
        if not raw:
            return []

        # Unwrap the outer list: [["Adobe","LinkedIn",...]] → ["Adobe","LinkedIn",...]
        if isinstance(raw[0], list):
            names = raw[0]
        elif isinstance(raw[0], str):
            names = raw
        else:
            return self._parse_xon_dicts(raw)

        results = []
        for name in names:
            if not isinstance(name, str) or not name.strip():
                continue
            # Enrich with known data classes so severity is meaningful
            known = _KNOWN_BREACH_DATA.get(name.strip(), {})
            results.append({
                "Name":        name.strip(),
                "Title":       name.strip(),
                "Domain":      known.get("domain", ""),
                "BreachDate":  known.get("date", "unknown"),
                "PwnCount":    known.get("count", 0),
                "DataClasses": known.get("classes", []),
                "IsVerified":  True,
                "_source":     "XposedOrNot",
            })
        return results

    def _parse_xon_dicts(self, entries: List) -> List[Dict[str, Any]]:
        """Parse XposedOrNot Plus / analytics response (dict format)."""
        results = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name        = entry.get("name", entry.get("Name", "Unknown"))
            date        = entry.get("date", entry.get("BreachDate", "unknown"))
            classes_raw = entry.get("exposedData", entry.get("DataClasses", ""))
            pwn_count   = int(entry.get("pwnCount", entry.get("PwnCount", 0)))

            if isinstance(classes_raw, str):
                data_classes = [c.strip() for c in classes_raw.split(",") if c.strip()]
            elif isinstance(classes_raw, list):
                data_classes = classes_raw
            else:
                data_classes = []

            results.append({
                "Name":        name,
                "Title":       name,
                "Domain":      "",
                "BreachDate":  date,
                "PwnCount":    pwn_count,
                "DataClasses": data_classes,
                "IsVerified":  True,
                "_source":     "XposedOrNot",
            })
        return results

    # ── HIBP (optional paid key) ───────────────────────────────────────────────

    async def _check_hibp(self, email: str) -> List[Dict[str, Any]]:
        """
        Query HaveIBeenPwned v3 API.
        Only called when HIBP_API_KEY is set in .env.
        """
        url = f"{self.HIBP_BASE}/breachedaccount/{email}"
        params = {"truncateResponse": "false", "includeUnverified": "false"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    url, headers=self._hibp_headers, params=params
                )
                if resp.status_code == 404:
                    return []
                if resp.status_code == 429:
                    await asyncio.sleep(1.5)
                    return await self._check_hibp(email)
                if resp.status_code == 401:
                    return []   # bad/missing key — degrade silently
                resp.raise_for_status()
                breaches = resp.json()
                # Tag source so deduplication can prefer HIBP metadata
                for b in breaches:
                    b["_source"] = "HIBP"
                return breaches
            except Exception:
                return []

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def classify_breach_severity(self, breach: Dict[str, Any]) -> str:
        """Assign severity based on what data types were exposed."""
        exposed = set(breach.get("DataClasses", []))
        if exposed & {"Passwords", "Credit cards", "Bank account numbers"}:
            return "critical"
        if exposed & {"Physical addresses", "Phone numbers", "Dates of birth",
                      "Social security numbers", "Government issued IDs"}:
            return "high"
        if exposed & {"Email addresses", "Usernames", "IP addresses",
                      "Passwords", "email", "password"}:
            return "medium"
        return "low"

    def format_findings(
        self, breaches: List[Dict], email: str
    ) -> List[Dict[str, Any]]:
        """Convert raw breach records to DataShield finding dicts."""
        findings = []
        for b in breaches:
            severity = self.classify_breach_severity(b)
            source   = b.get("_source", "Breach DB")
            name     = b.get("Name", b.get("Title", "Unknown"))
            domain   = b.get("Domain", "")
            date     = b.get("BreachDate", "unknown date")
            classes  = b.get("DataClasses", [])
            count    = b.get("PwnCount", 0)

            findings.append({
                "finding_type":   "breach",
                "source_name":    name,
                "source_url":     f"https://{domain}" if domain else "",
                "source_domain":  domain,
                "source_title":   f"Data breach: {b.get('Title', name)} [{source}]",
                "severity":       severity,
                "risk_score": {
                    "critical": 9.5, "high": 7.5,
                    "medium": 5.0,   "low": 2.5,
                }[severity],
                "description": (
                    f"Email found in the '{name}' data breach ({source}). "
                    f"Breach date: {date}. "
                    f"Exposed data: {', '.join(classes) if classes else 'unknown'}."
                ),
                "exposed_data_types": [
                    d.lower().replace(" ", "_") for d in classes
                ],
                "credential_exposure":    "Passwords" in classes or "password" in classes,
                "financial_risk":         "Credit cards" in classes,
                "identity_theft_risk":    severity in ("critical", "high"),
                "government_id_exposure": any(
                    t in classes for t in [
                        "Social security numbers", "Passport numbers",
                        "Government issued IDs",
                    ]
                ),
                "raw_data": {
                    "breach_name":  name,
                    "breach_date":  date,
                    "pwn_count":    count,
                    "data_classes": classes,
                    "is_verified":  b.get("IsVerified", True),
                    "source":       source,
                },
                "snippet": (
                    f"Breach: {name} | Date: {date} | "
                    f"{count:,} accounts affected | Source: {source}"
                ),
            })
        return findings

    def _mock_breach_check(self, email: str) -> List[Dict]:
        """
        Legacy fallback — now unused since XposedOrNot gives real data for free.
        Kept for backwards compatibility.
        """
        return []
