"""
DataShield OSINT - Search Engine Discovery Module
Searches Google and Bing for publicly indexed personal information
"""
import asyncio
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, quote_plus
import httpx

from app.core.config import settings


class SearchEngineScanner:
    """
    Searches public search engine indexes for personal information exposure.
    
    Uses Google Custom Search API and Bing Search API.
    All searches are strictly limited to public, indexed content.
    """

    GOOGLE_API_BASE = "https://www.googleapis.com/customsearch/v1"
    BING_API_BASE = "https://api.bing.microsoft.com/v7.0/search"

    # Safe domains to skip (not exposures)
    SAFE_DOMAINS = {
        "google.com", "bing.com", "wikipedia.org", "microsoft.com",
        "apple.com", "amazon.com", "youtube.com",
    }

    async def search_google(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """Search Google Custom Search API for the given query."""
        if not settings.GOOGLE_SEARCH_API_KEY or not settings.GOOGLE_SEARCH_ENGINE_ID:
            return self._mock_search_results(query)

        params = {
            "key": settings.GOOGLE_SEARCH_API_KEY,
            "cx": settings.GOOGLE_SEARCH_ENGINE_ID,
            "q": query,
            "num": min(num_results, 10),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(self.GOOGLE_API_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
                return data.get("items", [])
            except Exception:
                return []

    async def search_bing(self, query: str, count: int = 10) -> List[Dict[str, Any]]:
        """Search Bing for the given query."""
        if not settings.BING_SEARCH_API_KEY:
            return []

        headers = {"Ocp-Apim-Subscription-Key": settings.BING_SEARCH_API_KEY}
        params = {"q": query, "count": min(count, 50), "safeSearch": "Off"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(self.BING_API_BASE, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                return data.get("webPages", {}).get("value", [])
            except Exception:
                return []

    def build_queries(self, query_value: str, scan_type: str) -> List[str]:
        """Build targeted search queries for different data types."""
        queries = []

        if scan_type == "email":
            queries = [
                f'"{query_value}"',
                f'"{query_value}" site:pastebin.com OR site:paste.ee OR site:ghostbin.co',
                f'"{query_value}" "password" OR "credentials" OR "leaked"',
                f'"{query_value}" filetype:pdf OR filetype:xls OR filetype:csv',
            ]
        elif scan_type == "phone":
            queries = [
                f'"{query_value}"',
                f'"{query_value}" contact OR directory OR lookup',
            ]
        elif scan_type == "name":
            queries = [
                f'"{query_value}" site:truepeoplesearch.com OR site:whitepages.com OR site:spokeo.com',
                f'"{query_value}" address OR phone OR email',
            ]
        elif scan_type == "username":
            queries = [
                f'site:pastebin.com "{query_value}"',
                f'inurl:"{query_value}" social OR profile',
            ]
        else:
            queries = [f'"{query_value}"']

        return queries[:4]  # Limit to 4 queries to respect rate limits

    def filter_and_classify(self, results: List[Dict], query_value: str) -> List[Dict[str, Any]]:
        """Filter irrelevant results and classify exposure severity."""
        findings = []
        seen_domains = set()

        for r in results:
            url = r.get("link") or r.get("url", "")
            title = r.get("title", "")
            snippet = r.get("snippet") or r.get("snippet", "")

            if not url:
                continue

            domain = urlparse(url).netloc.lower().replace("www.", "")

            # Skip safe/known domains
            if domain in self.SAFE_DOMAINS:
                continue

            # Skip duplicates from same domain
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            # Check if query value actually appears in result
            combined_text = f"{title} {snippet}".lower()
            if query_value.lower() not in combined_text and query_value.split("@")[0].lower() not in combined_text:
                continue

            severity, risk_score = self._classify_result(domain, title, snippet)

            findings.append({
                "finding_type": "search_engine",
                "source_url": url,
                "source_domain": domain,
                "source_title": title,
                "source_name": "Google/Bing Search",
                "severity": severity,
                "risk_score": risk_score,
                "description": f"Personal information found publicly indexed on {domain}.",
                "exposed_data_types": ["email"] if "@" in query_value else ["personal_info"],
                "snippet": snippet[:500] if snippet else "",
                "reputation_risk": True,
                "identity_theft_risk": severity in ("critical", "high"),
            })

        return findings

    def _classify_result(self, domain: str, title: str, snippet: str) -> tuple:
        """Classify severity based on domain type and content keywords."""
        combined = f"{domain} {title} {snippet}".lower()

        if any(kw in combined for kw in ["password", "credential", "leaked", "breach", "hack", "dump"]):
            return "critical", 9.0
        if any(d in domain for d in ["pastebin", "paste", "hastebin", "ghostbin"]):
            return "critical", 8.5
        if any(kw in combined for kw in ["ssn", "passport", "aadhaar", "pan number", "bank account"]):
            return "critical", 9.5
        if any(kw in combined for kw in ["address", "phone", "personal", "private"]):
            return "high", 7.0
        if any(d in domain for d in ["whitepages", "spokeo", "truepeoplesearch", "intelius"]):
            return "high", 6.5
        return "medium", 4.0

    def _mock_search_results(self, query: str) -> List[Dict]:
        """Return empty list when API keys not configured."""
        return []
