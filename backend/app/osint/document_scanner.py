"""
DataShield OSINT - Document Exposure Scanner
Detects PDFs, spreadsheets, and public documents containing personal info
"""
import asyncio
import re
from typing import List, Dict, Any
from urllib.parse import urlparse
import httpx

from app.core.config import settings


class DocumentScanner:
    """
    Searches for publicly accessible documents (PDF, DOCX, XLS, CSV)
    that may contain personal information.
    
    Uses Google/Bing filetype: operators to find exposed documents.
    """

    DOCUMENT_TYPES = ["pdf", "doc", "docx", "xls", "xlsx", "csv", "txt"]

    def build_queries(self, query_value: str, scan_type: str) -> List[str]:
        """Build filetype-targeted search queries."""
        queries = []
        for doc_type in ["pdf", "xls", "csv", "doc"]:
            queries.append(f'"{query_value}" filetype:{doc_type}')
        return queries

    async def search_document_exposure(
        self, query_value: str, scan_type: str
    ) -> List[Dict[str, Any]]:
        """Search for documents containing personal information."""
        if not settings.GOOGLE_SEARCH_API_KEY:
            return []

        all_results = []
        queries = self.build_queries(query_value, scan_type)

        async with httpx.AsyncClient(timeout=15.0) as client:
            for query in queries[:3]:  # Limit API calls
                try:
                    resp = await client.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params={
                            "key": settings.GOOGLE_SEARCH_API_KEY,
                            "cx": settings.GOOGLE_SEARCH_ENGINE_ID,
                            "q": query,
                            "num": 10,
                        },
                    )
                    if resp.status_code == 200:
                        items = resp.json().get("items", [])
                        for item in items:
                            finding = self._parse_document_result(item, query_value)
                            if finding:
                                all_results.append(finding)
                    await asyncio.sleep(0.5)  # Rate limit
                except Exception:
                    continue

        return all_results

    def _parse_document_result(
        self, item: Dict, query_value: str
    ) -> Dict[str, Any] | None:
        """Parse a search result into a document finding."""
        url = item.get("link", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")

        if not url:
            return None

        domain = urlparse(url).netloc.replace("www.", "")
        ext = url.split(".")[-1].lower().split("?")[0]

        if ext not in self.DOCUMENT_TYPES:
            return None

        severity = self._classify_document_severity(ext, title, snippet, query_value)

        return {
            "finding_type": "document",
            "source_url": url,
            "source_domain": domain,
            "source_title": title,
            "source_name": f"Public Document ({ext.upper()})",
            "severity": severity,
            "risk_score": {"critical": 8.5, "high": 7.0, "medium": 5.0, "low": 3.0}[severity],
            "description": (
                f"A publicly accessible {ext.upper()} document on {domain} "
                f"appears to contain your personal information."
            ),
            "exposed_data_types": self._extract_data_types(snippet),
            "identity_theft_risk": severity in ("critical", "high"),
            "reputation_risk": True,
            "snippet": snippet[:500],
        }

    def _classify_document_severity(
        self, ext: str, title: str, snippet: str, query_value: str
    ) -> str:
        combined = f"{title} {snippet}".lower()
        if any(kw in combined for kw in ["password", "credential", "ssn", "passport", "aadhaar"]):
            return "critical"
        if ext in ("xls", "xlsx", "csv"):
            return "high"
        if any(kw in combined for kw in ["address", "phone", "salary", "bank"]):
            return "high"
        return "medium"

    def _extract_data_types(self, text: str) -> List[str]:
        types = []
        t = text.lower()
        if "email" in t or "@" in t:
            types.append("email")
        if "phone" in t or "mobile" in t:
            types.append("phone")
        if "address" in t:
            types.append("address")
        if "name" in t:
            types.append("name")
        if not types:
            types.append("personal_info")
        return types
