"""
DataShield OSINT - LinkedIn OSINT Module
Detects publicly-indexed LinkedIn profiles using Google dorks.

Strictly ethical and public-data-only:
  - No LinkedIn login or API credentials required
  - Uses Google Custom Search (or Bing) to find publicly indexed profiles
  - Only reads data that search engines have already indexed publicly
  - Respects LinkedIn robots.txt — does NOT directly scrape linkedin.com
"""
import asyncio
import re
from typing import List, Dict, Any, Optional
import httpx
from urllib.parse import quote_plus

from app.core.config import settings


# LinkedIn profile URL pattern
_LI_PROFILE_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-_%]+)/?",
    re.IGNORECASE,
)


class LinkedInOSINT:
    """
    Find publicly-indexed LinkedIn profile references via search engine dorks.

    Strategy:
      1. Build targeted Google/Bing queries for the target (name, email, username).
      2. Filter results for linkedin.com/in/ URLs.
      3. Classify severity based on data visible in snippets.
    """

    GOOGLE_API_BASE = "https://www.googleapis.com/customsearch/v1"
    BING_API_BASE   = "https://api.bing.microsoft.com/v7.0/search"

    async def search(
        self,
        query_value: str,
        scan_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Search for LinkedIn profile exposure.

        Returns list of findings (same dict schema as other OSINT modules).
        Always returns results (empty list if nothing found — never raises).
        """
        queries = self._build_queries(query_value, scan_type)
        raw_results: List[Dict] = []

        for q in queries:
            results = await self._search_google(q)
            if not results:
                results = await self._search_bing(q)
            raw_results.extend(results)
            await asyncio.sleep(0.4)  # gentle rate limiting

        return self._extract_findings(raw_results, query_value)

    # ── Private helpers ────────────────────────────────────────────────────

    def _build_queries(self, value: str, scan_type: str) -> List[str]:
        """Build dork queries targeting LinkedIn."""
        if scan_type == "email":
            username = value.split("@")[0]
            return [
                f'site:linkedin.com/in "{username}"',
                f'site:linkedin.com "{value}"',
            ]
        elif scan_type == "name":
            return [
                f'site:linkedin.com/in "{value}"',
                f'site:linkedin.com/in {value}',
            ]
        elif scan_type == "username":
            return [
                f'site:linkedin.com/in "{value}"',
                f'site:linkedin.com/in/{value}',
            ]
        else:
            return [f'site:linkedin.com/in "{value}"']

    async def _search_google(self, query: str) -> List[Dict]:
        if not settings.GOOGLE_SEARCH_API_KEY or not settings.GOOGLE_SEARCH_ENGINE_ID:
            return []
        params = {
            "key": settings.GOOGLE_SEARCH_API_KEY,
            "cx":  settings.GOOGLE_SEARCH_ENGINE_ID,
            "q":   query,
            "num": 5,
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.GOOGLE_API_BASE, params=params)
                resp.raise_for_status()
                return resp.json().get("items", [])
        except Exception:
            return []

    async def _search_bing(self, query: str) -> List[Dict]:
        if not settings.BING_SEARCH_API_KEY:
            return []
        headers = {"Ocp-Apim-Subscription-Key": settings.BING_SEARCH_API_KEY}
        params  = {"q": query, "count": 5}
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.BING_API_BASE, headers=headers, params=params)
                resp.raise_for_status()
                return resp.json().get("webPages", {}).get("value", [])
        except Exception:
            return []

    def _extract_findings(
        self,
        results: List[Dict],
        query_value: str,
    ) -> List[Dict[str, Any]]:
        """Parse search results and build DataShield finding dicts."""
        findings: List[Dict[str, Any]] = []
        seen_urls: set = set()

        for item in results:
            url     = item.get("link") or item.get("url", "")
            title   = item.get("title", "")
            snippet = item.get("snippet", "")

            if not url or url in seen_urls:
                continue
            if "linkedin.com/in/" not in url.lower():
                continue

            seen_urls.add(url)

            # Extract data hints from the snippet
            exposed_types   = ["profile"]
            identity_risk   = False
            financial_risk  = False
            snippet_lower   = snippet.lower()

            if any(kw in snippet_lower for kw in ["email", "@"]):
                exposed_types.append("email")
                identity_risk = True
            if any(kw in snippet_lower for kw in ["phone", "mobile", "contact"]):
                exposed_types.append("phone")
                identity_risk = True
            if any(kw in snippet_lower for kw in ["address", "location", "city"]):
                exposed_types.append("location")
            if any(kw in snippet_lower for kw in ["experience", "work", "company", "employer"]):
                exposed_types.append("employment_history")
            if any(kw in snippet_lower for kw in ["education", "university", "degree"]):
                exposed_types.append("education")

            # Higher severity if contact info is directly visible in snippet
            has_contact = "email" in exposed_types or "phone" in exposed_types
            severity   = "high"   if has_contact else "medium"
            risk_score = 7.5 if has_contact else 5.0

            findings.append({
                "finding_type":          "social_media",
                "source_url":            url,
                "source_domain":         "linkedin.com",
                "source_title":          title or f"LinkedIn Profile",
                "source_name":           "LinkedIn",
                "severity":              severity,
                "risk_score":            risk_score,
                "description": (
                    f"LinkedIn professional profile found publicly indexed. "
                    f"Visible data: {', '.join(exposed_types)}. "
                    "Professional profiles can expose employment history, location, "
                    "and contact details to anyone on the internet."
                ),
                "exposed_data_types":    exposed_types,
                "identity_theft_risk":   identity_risk,
                "financial_risk":        financial_risk,
                "reputation_risk":       True,
                "credential_exposure":   False,
                "government_id_exposure": False,
                "snippet":               snippet[:500],
                "raw_data": {
                    "url":     url,
                    "title":   title,
                    "snippet": snippet,
                    "query":   query_value,
                },
            })

        return findings


async def check_linkedin_exposure(
    query_value: str,
    scan_type: str = "email",
) -> List[Dict[str, Any]]:
    """
    Top-level convenience function called by the OSINT engine.

    Returns an empty list if no API keys are configured (degrades gracefully).
    """
    scanner = LinkedInOSINT()
    return await scanner.search(query_value, scan_type)
