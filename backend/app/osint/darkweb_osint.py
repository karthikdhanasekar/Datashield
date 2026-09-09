"""
DataShield OSINT - Dark Web Indicator Module
Searches publicly accessible Tor/dark-web indexes for personal data exposure.

Sources used (all ethical, publicly accessible via clearnet):
  - Ahmia.fi  — publicly indexed Tor search engine (clearnet HTTPS API)
  - IntelX.io — public search for breached data indicators (free tier)
  - DarkSearch.io — publicly accessible dark web search (free tier)

This module does NOT:
  - Connect directly to the Tor network
  - Access illegal or CSAM content
  - Scrape private or restricted APIs

It ONLY searches publicly available index endpoints the same way
a journalist or researcher would.
"""
import asyncio
import re
from typing import List, Dict, Any
import httpx
from urllib.parse import quote_plus

from app.core.config import settings


# Regex to roughly detect data-dump-like content in snippets
_DUMP_KEYWORDS = re.compile(
    r"\b(password|passwd|credential|hash|plaintext|dump|breach|"
    r"leaked|combo\s*list|database\s*dump|db\s*leak|ssn|aadhaar|"
    r"credit\s*card|cvv|bank\s*account)\b",
    re.IGNORECASE,
)


class DarkWebOSINT:
    """
    Queries publicly accessible dark web indexes (via clearnet HTTPS) for
    indicators that personal data appears in Tor-hosted leak sites.

    All three back-ends degrade gracefully when unavailable.
    """

    AHMIA_BASE       = "https://ahmia.fi/search"
    DARKSEARCH_BASE  = "https://darksearch.io/api/search"   # may be blocked in some networks
    INTELX_BASE      = "https://2.intelx.io"

    def __init__(self):
        # IntelX free public key (rate-limited, no registration needed)
        self._intelx_key = getattr(settings, "INTELX_API_KEY", "")

    async def search(
        self,
        query_value: str,
        scan_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Run all three back-ends concurrently and merge results.
        Returns empty list on total failure — never raises.
        """
        tasks = [
            self._search_ahmia(query_value),
            self._search_darksearch(query_value),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        findings: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, list):
                findings.extend(r)

        # Deduplicate by .onion domain
        return _dedupe(findings)

    # ── Ahmia.fi ─────────────────────────────────────────────────────────────

    async def _search_ahmia(self, query: str) -> List[Dict[str, Any]]:
        """
        Search Ahmia.fi — the most established public Tor search index.
        Uses their public clearnet HTTPS endpoint.
        """
        params = {"q": query}
        headers = {
            "User-Agent": "DataShield-OSINT/1.0 (privacy-research; ethical use)",
            "Accept": "text/html",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(self.AHMIA_BASE, params=params, headers=headers)
                if resp.status_code != 200:
                    return []
                return self._parse_ahmia_html(resp.text, query)
        except Exception:
            return []

    def _parse_ahmia_html(self, html: str, query: str) -> List[Dict[str, Any]]:
        """
        Extract .onion result titles and URLs from Ahmia HTML response.
        We only look at visible text, never execute scripts.
        """
        findings: List[Dict[str, Any]] = []

        # Simple regex extraction — no DOM parsing to avoid lxml dependency
        result_blocks = re.findall(
            r'<li class="result">(.*?)</li>',
            html,
            re.DOTALL,
        )

        for block in result_blocks[:10]:  # cap at 10 results
            # Extract URL
            url_match  = re.search(r'href="(http[^"]+)"', block)
            title_match = re.search(r'<h4[^>]*>(.*?)</h4>', block, re.DOTALL)
            desc_match  = re.search(r'<p[^>]*>(.*?)</p>',   block, re.DOTALL)

            url   = url_match.group(1).strip()   if url_match   else ""
            title = _strip_tags(title_match.group(1)) if title_match else "Dark Web Result"
            desc  = _strip_tags(desc_match.group(1))  if desc_match  else ""

            if not url or query.lower() not in (title + desc).lower():
                continue

            severity, risk_score = _classify_dark_result(url, title, desc)

            findings.append(_build_finding(
                url=url,
                title=title,
                snippet=desc[:400],
                severity=severity,
                risk_score=risk_score,
                source="Ahmia (Tor Index)",
                query=query,
            ))

        return findings

    # ── DarkSearch.io ─────────────────────────────────────────────────────────

    async def _search_darksearch(self, query: str) -> List[Dict[str, Any]]:
        """
        Query DarkSearch.io public API (no key required for limited use).
        """
        params = {"query": query, "page": 1}
        headers = {"User-Agent": "DataShield-OSINT/1.0"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    self.DARKSEARCH_BASE,
                    params=params,
                    headers=headers,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                return self._parse_darksearch(data, query)
        except Exception:
            return []

    def _parse_darksearch(
        self,
        data: Dict,
        query: str,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        hits = data.get("data") or data.get("results") or []

        for hit in hits[:8]:
            url   = hit.get("link",    hit.get("url",   ""))
            title = hit.get("title",   "Dark Web Page")
            desc  = hit.get("snippet", hit.get("description", ""))

            if not url:
                continue

            severity, risk_score = _classify_dark_result(url, title, desc)
            findings.append(_build_finding(
                url=url,
                title=title,
                snippet=desc[:400],
                severity=severity,
                risk_score=risk_score,
                source="DarkSearch.io",
                query=query,
            ))

        return findings


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _classify_dark_result(url: str, title: str, snippet: str) -> tuple:
    """Assign severity/risk based on URL type and content keywords."""
    combined = f"{url} {title} {snippet}".lower()

    if _DUMP_KEYWORDS.search(combined):
        return "critical", 9.5
    if any(kw in combined for kw in ["forum", "market", "shop", "vendor"]):
        return "high", 7.5
    if ".onion" in url.lower():
        return "high", 7.0
    return "medium", 5.0


def _build_finding(
    url: str,
    title: str,
    snippet: str,
    severity: str,
    risk_score: float,
    source: str,
    query: str,
) -> Dict[str, Any]:
    return {
        "finding_type":           "dark_web_indicator",
        "source_url":             url,
        "source_domain":          _onion_domain(url),
        "source_title":           title,
        "source_name":            source,
        "severity":               severity,
        "risk_score":             risk_score,
        "description": (
            f"Personal data indicator found on dark web index ({source}). "
            "This suggests the data may appear on Tor-hosted leak sites or "
            "underground forums. Immediate action recommended."
        ),
        "exposed_data_types":     ["dark_web_mention"],
        "identity_theft_risk":    severity in ("critical", "high"),
        "financial_risk":         "critical" == severity,
        "reputation_risk":        True,
        "credential_exposure":    _DUMP_KEYWORDS.search(snippet + title) is not None,
        "government_id_exposure": False,
        "snippet":                snippet,
        "raw_data":               {"url": url, "title": title, "source": source, "query": query},
    }


def _onion_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc or "unknown.onion"
    except Exception:
        return "unknown.onion"


def _strip_tags(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", " ", text).strip()


def _dedupe(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for f in findings:
        key = f.get("source_url", "") or f.get("source_domain", "")
        if key and key not in seen:
            seen.add(key)
            out.append(f)
    return out


async def check_dark_web_exposure(
    query_value: str,
    scan_type: str = "email",
) -> List[Dict[str, Any]]:
    """
    Top-level convenience function called by the OSINT engine.
    Always returns a list (empty if nothing found). Never raises.
    """
    scanner = DarkWebOSINT()
    return await scanner.search(query_value, scan_type)
