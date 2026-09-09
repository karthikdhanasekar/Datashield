"""
DataShield OSINT - Instagram & Facebook OSINT Module
Detects public profile exposure on Instagram and Facebook.

Approach:
  - Instagram: direct HTTP HEAD request to public profile URL
    (no login required for existence check on public profiles)
  - Facebook: Google/Bing search dork (facebook.com does not allow direct
    unauthenticated scraping; we only surface publicly indexed content)

Strictly ethical and public-data-only:
  - No login, no private data access
  - HEAD requests only (no page body parsing)
  - Rate limited to avoid platform abuse
"""
import asyncio
from typing import List, Dict, Any
import httpx
from urllib.parse import quote

from app.core.config import settings


class InstagramOSINT:
    """
    Check Instagram public profile existence and index Facebook via search dorks.
    """

    GOOGLE_API_BASE = "https://www.googleapis.com/customsearch/v1"
    BING_API_BASE   = "https://api.bing.microsoft.com/v7.0/search"

    async def check_instagram(self, username: str) -> List[Dict[str, Any]]:
        """
        Check if an Instagram profile is publicly accessible.
        Uses a HEAD request to instagram.com — no login, no scraping body content.
        """
        url = f"https://www.instagram.com/{quote(username)}/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        try:
            async with httpx.AsyncClient(
                timeout=12.0,
                follow_redirects=True,
                headers=headers,
            ) as client:
                resp = await client.head(url)
                # 200 = public profile exists; 404 = not found; 302 to /login = private
                if resp.status_code == 200 and "/login" not in str(resp.url):
                    return [self._instagram_finding(username, url)]
        except Exception:
            pass
        return []

    async def check_facebook(
        self,
        query_value: str,
        scan_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Search for publicly indexed Facebook profile references via search dorks.
        Does NOT directly scrape facebook.com.
        """
        queries = self._build_fb_queries(query_value, scan_type)
        results: List[Dict] = []

        for q in queries:
            items = await self._search_google(q)
            if not items:
                items = await self._search_bing(q)
            results.extend(items)
            await asyncio.sleep(0.4)

        return self._extract_fb_findings(results, query_value)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _instagram_finding(self, username: str, url: str) -> Dict[str, Any]:
        return {
            "finding_type":           "social_media",
            "source_url":             url,
            "source_domain":          "instagram.com",
            "source_title":           f"Instagram Profile: @{username}",
            "source_name":            "Instagram",
            "severity":               "medium",
            "risk_score":             4.5,
            "description": (
                f"Instagram account @{username} is publicly accessible. "
                "Public accounts expose photos, follower counts, bio, and "
                "linked contact information to anyone on the internet."
            ),
            "exposed_data_types":     ["username", "photos", "bio"],
            "identity_theft_risk":    False,
            "financial_risk":         False,
            "reputation_risk":        True,
            "credential_exposure":    False,
            "government_id_exposure": False,
            "snippet":                f"Public Instagram account found at {url}",
        }

    def _build_fb_queries(self, value: str, scan_type: str) -> List[str]:
        if scan_type == "name":
            return [
                f'site:facebook.com "{value}"',
                f'site:facebook.com/people "{value}"',
            ]
        elif scan_type == "email":
            username = value.split("@")[0]
            return [f'site:facebook.com "{username}"']
        else:
            return [f'site:facebook.com "{value}"']

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

    def _extract_fb_findings(
        self,
        results: List[Dict],
        query_value: str,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        seen: set = set()

        for item in results:
            url     = item.get("link") or item.get("url", "")
            title   = item.get("title", "")
            snippet = item.get("snippet", "")

            if not url or url in seen:
                continue
            if "facebook.com" not in url.lower():
                continue
            # Skip business pages & events — these are not personal data
            if any(p in url.lower() for p in ["/events/", "/groups/", "/pages/"]):
                continue

            seen.add(url)

            exposed_types = ["profile"]
            snippet_lower = snippet.lower()

            if any(kw in snippet_lower for kw in ["phone", "mobile", "contact"]):
                exposed_types.append("phone")
            if any(kw in snippet_lower for kw in ["email", "@"]):
                exposed_types.append("email")
            if any(kw in snippet_lower for kw in ["address", "location", "city", "hometown"]):
                exposed_types.append("location")

            has_contact = any(t in exposed_types for t in ["email", "phone"])
            severity    = "high" if has_contact else "medium"
            risk_score  = 7.0   if has_contact else 4.5

            findings.append({
                "finding_type":           "social_media",
                "source_url":             url,
                "source_domain":          "facebook.com",
                "source_title":           title or "Facebook Profile",
                "source_name":            "Facebook",
                "severity":               severity,
                "risk_score":             risk_score,
                "description": (
                    f"Facebook profile or page found publicly indexed. "
                    f"Visible data: {', '.join(exposed_types)}."
                ),
                "exposed_data_types":     exposed_types,
                "identity_theft_risk":    has_contact,
                "financial_risk":         False,
                "reputation_risk":        True,
                "credential_exposure":    False,
                "government_id_exposure": False,
                "snippet":                snippet[:500],
                "raw_data":               {"url": url, "title": title},
            })

        return findings


async def check_instagram_exposure(username: str) -> List[Dict[str, Any]]:
    """Convenience function for OSINT engine — check Instagram."""
    scanner = InstagramOSINT()
    return await scanner.check_instagram(username)


async def check_facebook_exposure(
    query_value: str,
    scan_type: str = "name",
) -> List[Dict[str, Any]]:
    """Convenience function for OSINT engine — check Facebook via dorks."""
    scanner = InstagramOSINT()
    return await scanner.check_facebook(query_value, scan_type)
