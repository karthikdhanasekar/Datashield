"""
DataShield OSINT - Pastebin / Paste Site Scanner
-------------------------------------------------
Searches public paste aggregators and archive sites for exposed
personal data (emails, phone numbers, usernames, IDs).

Sources used (all public / no auth):
  - psbdmp.ws   — Pastebin dump search (public API)
  - paste.ee    — Public paste search
  - pastehunter — Uses Google Custom Search for paste sites
  - Google dork — site:pastebin.com "query"

No scraping of private or unlisted pastes.
"""
import asyncio
import re
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urlparse
import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Paste site domains — used for severity classification
PASTE_DOMAINS = {
    "pastebin.com", "paste.ee", "ghostbin.co", "hastebin.com",
    "psbdmp.ws", "controlc.com", "justpaste.it", "paste.org",
    "0bin.net", "dpaste.org", "pastecode.io",
}


async def search_pastes(query_value: str, scan_type: str) -> List[Dict[str, Any]]:
    """
    Search paste sites for the given query value.
    Returns DataShield findings for each paste that contains the target data.

    Sources tried (in order):
      1. psbdmp.cc  — Pastebin dump search API (free, no key)
      2. Google CSE dork — site:pastebin.com (requires Google API key)
    """
    findings = []

    tasks = [
        _search_psbdmp(query_value),
        _search_via_google_dork(query_value, scan_type),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            findings.extend(result)

    # Deduplicate by URL
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for f in findings:
        url = f.get("source_url", "")
        if url not in seen:
            seen.add(url)
            unique.append(f)

    return unique


async def _search_psbdmp(query: str) -> List[Dict[str, Any]]:
    """
    Search psbdmp.ws — a public Pastebin dump search engine.
    API: https://psbdmp.ws/api/v3/search/<query>
    Free, no key required.

    Falls back to the alternative endpoint if DNS fails in container.
    """
    endpoints = [
        f"https://psbdmp.cc/api/v3/search/{quote_plus(query)}",   # .cc resolves; .ws does not
        f"https://psbdmp.ws/api/v3/search/{quote_plus(query)}",   # fallback if .cc fails
    ]
    findings = []

    for url in endpoints:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers={"User-Agent": "DataShield-OSINT/1.0"})
                if resp.status_code != 200:
                    continue

                data = resp.json()
                pastes = data.get("data", [])

                for paste in pastes[:10]:
                    paste_id    = paste.get("id", "")
                    paste_url   = f"https://pastebin.com/{paste_id}" if paste_id else ""
                    tags        = paste.get("tags", "")
                    snippet_txt = paste.get("text", "")[:300]
                    upload_time = paste.get("time", "")

                    if query.lower() not in snippet_txt.lower():
                        continue

                    findings.append({
                        "finding_type":           "paste_site",
                        "source_name":            "Pastebin (psbdmp)",
                        "source_url":             paste_url,
                        "source_domain":          "pastebin.com",
                        "source_title":           "Data found in public Pastebin paste",
                        "severity":               "critical",
                        "risk_score":             9.0,
                        "description": (
                            f"Personal data found in a public Pastebin paste. "
                            f"Paste ID: {paste_id}. "
                            "Public pastes containing personal data are common indicators of a data leak."
                        ),
                        "exposed_data_types":     _infer_data_types(snippet_txt),
                        "reputation_risk":        True,
                        "identity_theft_risk":    True,
                        "financial_risk":         False,
                        "credential_exposure":    _has_credentials(snippet_txt),
                        "government_id_exposure": False,
                        "snippet":                snippet_txt,
                        "raw_data": {
                            "paste_id":    paste_id,
                            "tags":        tags,
                            "upload_time": upload_time,
                            "source":      "psbdmp.ws",
                        },
                    })
                # If we got a response, don't try the mirror
                break
        except Exception as e:
            logger.warning("psbdmp search failed", url=url, error=str(e))
            continue

    return findings


async def _search_via_google_dork(query: str, scan_type: str) -> List[Dict[str, Any]]:
    """
    Use Google Custom Search API with paste site dorks.
    Only runs if GOOGLE_SEARCH_API_KEY is configured.
    """
    if not settings.GOOGLE_SEARCH_API_KEY or not settings.GOOGLE_SEARCH_ENGINE_ID:
        return []

    findings = []
    paste_dork = (
        f'"{query}" site:pastebin.com OR site:paste.ee OR '
        f'site:ghostbin.co OR site:hastebin.com OR site:dpaste.org'
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": settings.GOOGLE_SEARCH_API_KEY,
                    "cx": settings.GOOGLE_SEARCH_ENGINE_ID,
                    "q": paste_dork,
                    "num": 10,
                },
            )
            if resp.status_code != 200:
                return []

            items = resp.json().get("items", [])
            for item in items:
                url = item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                domain = urlparse(url).netloc.replace("www.", "")

                if domain not in PASTE_DOMAINS:
                    continue

                findings.append({
                    "finding_type": "paste_site",
                    "source_name": f"Paste Site – {domain}",
                    "source_url": url,
                    "source_domain": domain,
                    "source_title": title or f"Data found on {domain}",
                    "severity": "critical",
                    "risk_score": 9.0,
                    "description": (
                        f"Your personal data was found on a public paste site ({domain}). "
                        "This is a strong indicator of a data leak."
                    ),
                    "exposed_data_types": _infer_data_types(snippet),
                    "reputation_risk": True,
                    "identity_theft_risk": True,
                    "credential_exposure": _has_credentials(snippet),
                    "snippet": snippet[:500],
                    "raw_data": {"url": url, "title": title, "source": "google-dork"},
                })

        except Exception as e:
            logger.warning("Google paste dork failed", error=str(e))

    return findings


def _infer_data_types(text: str) -> List[str]:
    """Infer exposed data types from paste text."""
    types = []
    t = text.lower()
    if "@" in t:
        types.append("email")
    if re.search(r"\bpassword\b|\bpass:\b|\bpwd:\b", t):
        types.append("password")
    if re.search(r"\b\d{10,}\b", t):
        types.append("phone_number")
    if re.search(r"\bssn\b|\baadha\b|\baadhaar\b", t):
        types.append("government_id")
    if re.search(r"\bcard\b|\bcvv\b|\bexpiry\b", t):
        types.append("credit_card")
    if not types:
        types.append("personal_info")
    return types


def _has_credentials(text: str) -> bool:
    """Check if paste likely contains passwords or credentials."""
    return bool(re.search(r"\bpassword\b|\bpass:\b|\bpwd:\b|\bhash\b|\bcredential\b", text.lower()))
