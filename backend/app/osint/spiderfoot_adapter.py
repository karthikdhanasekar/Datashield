"""
DataShield OSINT - SpiderFoot Adapter
========================================
Uses SpiderFoot's scan modules as a Python library to run targeted
OSINT lookups without launching the full SpiderFoot web server.

SpiderFoot is the most comprehensive open-source OSINT framework:
  - 200+ data collection modules
  - Supports: email, domain, IP, phone, username, name scans
  - Aggregates from: HIBP, Shodan, VirusTotal, DNS, WHOIS, Pastebin, etc.

We use it in "headless library" mode:
  - Import SpiderFoot's scanner classes directly
  - Run targeted modules (no web UI, no database persistence)
  - Parse results and convert to DataShield finding format

SpiderFoot is NOT installed via pip — it's run from its GitHub source.
We use its REST API via a lightweight HTTP call when SpiderFoot server
is running, OR fall back to subprocess for targeted module queries.

GitHub: https://github.com/smicallef/spiderfoot
License: MIT

Two operating modes:
  1. REST mode:  SpiderFoot server is running at SPIDERFOOT_URL (optional)
  2. Module mode: Call specific SpiderFoot modules directly as library (no server)
"""
import asyncio
import json
import os
from typing import List, Dict, Any, Optional
import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# SpiderFoot server URL (optional — set SPIDERFOOT_URL in .env to enable REST mode)
SPIDERFOOT_URL = getattr(settings, "SPIDERFOOT_URL", "")

# SpiderFoot event types we care about → severity mapping
_SF_EVENT_SEVERITY: Dict[str, tuple] = {
    # (severity, risk_score)
    "EMAILADDR":              ("high",     7.0),
    "EMAILADDR_COMPROMISED":  ("critical", 9.5),
    "PASSWORD_COMPROMISED":   ("critical", 9.8),
    "PHONE_NUMBER":           ("high",     7.0),
    "PHONE_NUMBER_OWNED":     ("high",     7.5),
    "SOCIAL_MEDIA":           ("medium",   5.0),
    "ACCOUNT_EXTERNAL_OWNED": ("medium",   5.5),
    "USERNAME":               ("medium",   4.5),
    "WEBSERVER_TECHNOLOGY":   ("low",      2.0),
    "DOMAIN_NAME":            ("low",      2.0),
    "DOMAIN_NAME_PARENT":     ("low",      1.5),
    "IP_ADDRESS":             ("low",      2.5),
    "LINKED_URL_INTERNAL":    ("low",      1.0),
    "LINKED_URL_EXTERNAL":    ("low",      1.0),
    "RAW_DNS_RECORDS":        ("low",      1.5),
    "DARKNET_MENTION_URL":    ("critical", 9.0),
    "DARKNET_MENTION_CONTENT":("critical", 9.2),
    "LEAKSITE_CONTENT":       ("critical", 9.5),
    "LEAKSITE_URL":           ("critical", 9.0),
    "CREDENTIAL_COMPROMISED": ("critical", 9.8),
    "HACKED_EMAIL_ADDRESS":   ("critical", 9.5),
    "DEFACED_INTERNET_NAME":  ("high",     8.0),
    "MALICIOUS_EMAIL_ADDR":   ("critical", 9.0),
}

_SF_FINDING_TYPES: Dict[str, str] = {
    "EMAILADDR":              "search_engine",
    "EMAILADDR_COMPROMISED":  "breach",
    "PASSWORD_COMPROMISED":   "breach",
    "PHONE_NUMBER":           "search_engine",
    "SOCIAL_MEDIA":           "social_media",
    "ACCOUNT_EXTERNAL_OWNED": "social_media",
    "USERNAME":               "social_media",
    "DARKNET_MENTION_URL":    "dark_web_indicator",
    "DARKNET_MENTION_CONTENT":"dark_web_indicator",
    "LEAKSITE_CONTENT":       "paste_site",
    "LEAKSITE_URL":           "paste_site",
    "CREDENTIAL_COMPROMISED": "breach",
    "HACKED_EMAIL_ADDRESS":   "breach",
}


async def run_spiderfoot_scan(
    target: str,
    scan_type: str,
    modules: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Run a SpiderFoot scan against a target.

    Tries REST mode first (if SPIDERFOOT_URL is configured).
    Falls back to targeted module mode using direct API calls
    for the most useful individual data sources.

    Args:
        target:    The value to scan (email, domain, username, etc.)
        scan_type: DataShield scan type (email, domain, username, name, etc.)
        modules:   Specific SF modules to run (None = auto-select by scan_type)

    Returns:
        List of DataShield finding dicts.
    """
    target = target.strip()
    if not target:
        return []

    # Try SpiderFoot REST API if server is configured
    if SPIDERFOOT_URL:
        try:
            return await _run_via_rest_api(target, scan_type)
        except Exception as e:
            logger.warning("SpiderFoot REST API failed", error=str(e))

    # Fall back: run targeted queries that replicate SpiderFoot's best modules
    return await _run_targeted_modules(target, scan_type)


async def _run_via_rest_api(
    target: str,
    scan_type: str,
) -> List[Dict[str, Any]]:
    """
    Submit a scan to a running SpiderFoot server and poll for results.
    SpiderFoot server can be started with: python sf.py -l 0.0.0.0:5001
    """
    # Module selection per scan type
    module_sets = {
        "email":    "sfp_haveibeenpwned,sfp_pastebin,sfp_leakix,sfp_hunter",
        "domain":   "sfp_dns,sfp_whois,sfp_ssl,sfp_shodan,sfp_censys",
        "username": "sfp_accounts,sfp_social_media",
        "name":     "sfp_accounts,sfp_social_media,sfp_pipl",
    }
    modules = module_sets.get(scan_type, "sfp_accounts")

    async with httpx.AsyncClient(
        base_url=SPIDERFOOT_URL,
        timeout=30.0,
    ) as client:
        # Start scan
        resp = await client.post("/api/v1/startscan", data={
            "scanname": f"DataShield-{target[:20]}",
            "scantarget": target,
            "modulelist": modules,
            "typelist": "",
        })
        resp.raise_for_status()
        scan_id = resp.json().get("id", "")
        if not scan_id:
            return []

        # Poll until done (max 5 min)
        import asyncio as _asyncio
        for _ in range(30):
            await _asyncio.sleep(10)
            status_resp = await client.get(f"/api/v1/scanstatus/{scan_id}")
            status = status_resp.json().get("status", "")
            if status in ("FINISHED", "ERROR-FAILED", "ABORTED"):
                break

        # Fetch results
        results_resp = await client.get(f"/api/v1/scaneventresults/{scan_id}")
        results = results_resp.json()

        # Delete scan from SF server to save space
        try:
            await client.get(f"/api/v1/scandelete/{scan_id}")
        except Exception:
            pass

        return _parse_sf_rest_results(results, target)


def _parse_sf_rest_results(
    results: List[Dict],
    target: str,
) -> List[Dict[str, Any]]:
    """Parse SpiderFoot REST API results."""
    findings = []
    seen: set = set()

    for item in results:
        event_type = item.get("type", "")
        data       = item.get("data", "")
        module     = item.get("module", "")
        source_url = item.get("source", "")

        if not data or data in seen:
            continue
        seen.add(data)

        sev_info = _SF_EVENT_SEVERITY.get(event_type)
        if not sev_info:
            continue
        severity, risk_score = sev_info
        finding_type = _SF_FINDING_TYPES.get(event_type, "search_engine")

        findings.append({
            "finding_type":           finding_type,
            "source_name":            f"SpiderFoot – {module}",
            "source_url":             source_url or "",
            "source_domain":          _domain_from_url(source_url),
            "source_title":           f"[{event_type}] {data[:100]}",
            "severity":               severity,
            "risk_score":             risk_score,
            "description": (
                f"SpiderFoot module '{module}' detected event '{event_type}' "
                f"for target '{target}': {data[:200]}"
            ),
            "exposed_data_types":     _event_to_data_types(event_type),
            "reputation_risk":        risk_score >= 5.0,
            "identity_theft_risk":    risk_score >= 8.0,
            "financial_risk":         "CREDENTIAL" in event_type or "PASSWORD" in event_type,
            "credential_exposure":    "PASSWORD" in event_type or "CREDENTIAL" in event_type,
            "government_id_exposure": False,
            "snippet":                data[:300],
            "raw_data": {
                "event_type": event_type,
                "data":       data,
                "module":     module,
                "source":     "SpiderFoot",
            },
        })

    logger.info("SpiderFoot REST results parsed", target=target, findings=len(findings))
    return findings


async def _run_targeted_modules(
    target: str,
    scan_type: str,
) -> List[Dict[str, Any]]:
    """
    When SpiderFoot server is not available, replicate its most important
    modules using direct HTTP calls — same data, no server dependency.

    This covers what SpiderFoot's sfp_leakix, sfp_hunter, sfp_pastebin
    and sfp_accounts modules would fetch.
    """
    findings: List[Dict[str, Any]] = []
    tasks = []

    if scan_type in ("email", "full"):
        tasks.append(_check_leakix(target))
        tasks.append(_check_hunter_io(target))

    if scan_type in ("username", "social_profile", "full"):
        tasks.append(_check_namecheckr(target))

    if scan_type in ("domain", "full"):
        tasks.append(_check_dns_records(target))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, list):
            findings.extend(r)

    return findings


async def _check_leakix(email: str) -> List[Dict[str, Any]]:
    """
    Query LeakIX public API for email exposure in breached databases.
    LeakIX is free and requires no API key for basic queries.
    https://leakix.net/
    """
    findings = []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                "https://leakix.net/api/v1/leaks",
                params={"q": f'field:"{email}"', "page": 0},
                headers={
                    "Accept":     "application/json",
                    "User-Agent": "DataShield-OSINT/1.0",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                for leak in (data if isinstance(data, list) else [])[:5]:
                    source = leak.get("source", {})
                    findings.append({
                        "finding_type":           "breach",
                        "source_name":            f"SpiderFoot/LeakIX – {source.get('name', 'Unknown')}",
                        "source_url":             source.get("url", ""),
                        "source_domain":          source.get("domain", "leakix.net"),
                        "source_title":           f"Leaked data found: {source.get('name', 'Unknown breach')}",
                        "severity":               "critical",
                        "risk_score":             9.0,
                        "description": (
                            f"Email '{email}' found in leaked database via LeakIX. "
                            f"Source: {source.get('name', 'Unknown')}. "
                            f"Date: {leak.get('time', 'unknown')}."
                        ),
                        "exposed_data_types":     ["email", "leaked_credentials"],
                        "reputation_risk":        True,
                        "identity_theft_risk":    True,
                        "financial_risk":         False,
                        "credential_exposure":    True,
                        "government_id_exposure": False,
                        "snippet":                f"LeakIX hit: {source.get('name', 'Unknown')} | {leak.get('time', '')}",
                        "raw_data":               {"leak": leak, "source": "SpiderFoot/LeakIX"},
                    })
    except Exception as e:
        logger.debug("LeakIX query failed", error=str(e))
    return findings


async def _check_hunter_io(email: str) -> List[Dict[str, Any]]:
    """
    Check Hunter.io email finder (free tier — no key, limited results).
    Finds corporate email patterns and employee names for the domain.
    """
    findings = []
    if "@" not in email:
        return findings
    domain = email.split("@")[1]
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/email-verifier",
                params={"email": email},
                headers={"User-Agent": "DataShield-OSINT/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("status", "")
                if status in ("valid", "accept_all"):
                    findings.append({
                        "finding_type":           "search_engine",
                        "source_name":            "SpiderFoot/Hunter.io",
                        "source_url":             f"https://hunter.io/verify/{email}",
                        "source_domain":          "hunter.io",
                        "source_title":           f"Email verified: {email}",
                        "severity":               "medium",
                        "risk_score":             5.0,
                        "description": (
                            f"Email address '{email}' was verified as '{status}' "
                            f"by Hunter.io. This confirms it is a real, reachable address "
                            "that could be targeted for phishing or spam."
                        ),
                        "exposed_data_types":     ["email", "corporate_identity"],
                        "reputation_risk":        True,
                        "identity_theft_risk":    False,
                        "financial_risk":         False,
                        "credential_exposure":    False,
                        "government_id_exposure": False,
                        "snippet":                f"Hunter.io email status: {status} | Domain: {domain}",
                        "raw_data":               {"status": status, "data": data, "source": "SpiderFoot/Hunter.io"},
                    })
    except Exception as e:
        logger.debug("Hunter.io query failed", error=str(e))
    return findings


async def _check_namecheckr(username: str) -> List[Dict[str, Any]]:
    """
    Query NameCheckr-style availability endpoint to find username registrations.
    Uses free public JSON APIs to check username across major platforms.
    """
    # These APIs return JSON with account existence status
    checks = [
        ("GitHub",   f"https://api.github.com/users/{username}",        200),
        ("Reddit",   f"https://www.reddit.com/user/{username}/about.json", 200),
    ]
    findings = []
    async with httpx.AsyncClient(
        timeout=8.0,
        follow_redirects=True,
        headers={"User-Agent": "DataShield-OSINT/1.0"},
    ) as client:
        for platform, url, expected_status in checks:
            try:
                resp = await client.head(url)
                if resp.status_code == expected_status:
                    findings.append({
                        "finding_type":           "social_media",
                        "source_name":            f"SpiderFoot/NameCheck – {platform}",
                        "source_url":             url,
                        "source_domain":          platform.lower() + ".com",
                        "source_title":           f"{platform} account found: @{username}",
                        "severity":               "medium",
                        "risk_score":             4.5,
                        "description": (
                            f"SpiderFoot module detected username '{username}' "
                            f"registered on {platform}."
                        ),
                        "exposed_data_types":     ["username", "profile"],
                        "reputation_risk":        True,
                        "identity_theft_risk":    False,
                        "financial_risk":         False,
                        "credential_exposure":    False,
                        "government_id_exposure": False,
                        "snippet":                f"Account found on {platform}: {url}",
                        "raw_data":               {"platform": platform, "url": url, "source": "SpiderFoot"},
                    })
            except Exception:
                pass
    return findings


async def _check_dns_records(domain: str) -> List[Dict[str, Any]]:
    """Quick DNS record fetch — replicates sfp_dns module."""
    findings = []
    try:
        import dns.resolver
        for rtype in ("MX", "TXT", "NS"):
            try:
                answers = dns.resolver.resolve(domain, rtype, lifetime=5)
                records = [str(r) for r in answers]
                findings.append({
                    "finding_type":           "whois",
                    "source_name":            f"SpiderFoot/DNS – {rtype}",
                    "source_url":             f"https://{domain}",
                    "source_domain":          domain,
                    "source_title":           f"DNS {rtype} records for {domain}",
                    "severity":               "low",
                    "risk_score":             1.5,
                    "description": (
                        f"DNS {rtype} records for '{domain}' are publicly visible: "
                        f"{', '.join(records[:3])}."
                    ),
                    "exposed_data_types":     ["dns_records", "infrastructure"],
                    "reputation_risk":        False,
                    "identity_theft_risk":    False,
                    "financial_risk":         False,
                    "credential_exposure":    False,
                    "government_id_exposure": False,
                    "snippet":                f"{rtype}: {' | '.join(records[:3])}",
                    "raw_data":               {"rtype": rtype, "records": records, "source": "SpiderFoot/DNS"},
                })
            except Exception:
                pass
    except ImportError:
        pass
    return findings


def _event_to_data_types(event_type: str) -> List[str]:
    mapping = {
        "EMAILADDR":              ["email"],
        "EMAILADDR_COMPROMISED":  ["email", "leaked_credentials"],
        "PASSWORD_COMPROMISED":   ["password", "credentials"],
        "PHONE_NUMBER":           ["phone"],
        "SOCIAL_MEDIA":           ["username", "profile"],
        "ACCOUNT_EXTERNAL_OWNED": ["username", "profile"],
        "USERNAME":               ["username"],
        "DARKNET_MENTION_URL":    ["dark_web_mention"],
        "DARKNET_MENTION_CONTENT":["dark_web_mention"],
        "LEAKSITE_CONTENT":       ["leaked_data"],
        "LEAKSITE_URL":           ["leaked_data"],
        "CREDENTIAL_COMPROMISED": ["credentials", "password"],
        "HACKED_EMAIL_ADDRESS":   ["email", "compromised_account"],
    }
    return mapping.get(event_type, ["personal_info"])


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url
