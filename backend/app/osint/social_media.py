"""
DataShield OSINT - Social Media Exposure Module
Detects public personal information exposure on social platforms
(Public data only — no authentication, no private data access)
"""
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from urllib.parse import quote


class SocialMediaScanner:
    """
    Checks public social media profiles for exposed personal information.
    
    Strictly public-only:
    - Checks if profiles are publicly discoverable
    - Analyzes publicly visible profile data
    - Never accesses private/authenticated data
    - Respects platform Terms of Service
    """

    PLATFORMS = {
        "github": {
            "api_url": "https://api.github.com/users/{username}",
            "profile_url": "https://github.com/{username}",
            "data_fields": ["name", "email", "location", "bio", "company"],
        },
        "reddit": {
            "api_url": "https://www.reddit.com/user/{username}/about.json",
            "profile_url": "https://reddit.com/u/{username}",
            "data_fields": ["name", "created_utc"],
        },
    }

    async def check_username_platforms(self, username: str) -> List[Dict[str, Any]]:
        """Check if username exists across multiple platforms."""
        tasks = [
            self._check_github(username),
            self._check_reddit(username),
            self._check_twitter_public(username),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        findings = []
        for r in results:
            if isinstance(r, dict) and r.get("found"):
                findings.append(r)
        return findings

    async def check_email_social(self, email: str) -> List[Dict[str, Any]]:
        """Check for email exposure on public platforms via search APIs."""
        findings = []
        username_part = email.split("@")[0]

        # Try username-based lookups
        platform_results = await self.check_username_platforms(username_part)
        for result in platform_results:
            result["description"] = (
                f"Username derived from your email found on {result.get('platform')}. "
                "Profile is publicly visible and may expose personal information."
            )
            findings.append(result)

        return findings

    async def _check_github(self, username: str) -> Dict[str, Any]:
        """Check if a GitHub profile is publicly available."""
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                headers = {"User-Agent": "DataShield-OSINT/1.0", "Accept": "application/vnd.github.v3+json"}
                resp = await client.get(
                    f"https://api.github.com/users/{quote(username)}",
                    headers=headers,
                )
                if resp.status_code != 200:
                    return {"found": False}

                data = resp.json()
                exposed_fields = []
                if data.get("email"):
                    exposed_fields.append("email")
                if data.get("location"):
                    exposed_fields.append("location")
                if data.get("name"):
                    exposed_fields.append("full_name")
                if data.get("company"):
                    exposed_fields.append("company")
                if data.get("bio"):
                    exposed_fields.append("bio")

                severity = "high" if "email" in exposed_fields else "medium" if exposed_fields else "low"

                return {
                    "found": True,
                    "platform": "GitHub",
                    "finding_type": "social_media",
                    "source_url": f"https://github.com/{username}",
                    "source_domain": "github.com",
                    "source_title": f"GitHub Profile: {data.get('name', username)}",
                    "source_name": "GitHub",
                    "severity": severity,
                    "risk_score": 6.0 if "email" in exposed_fields else 3.5,
                    "exposed_data_types": exposed_fields,
                    "reputation_risk": True,
                    "snippet": (
                        f"Public GitHub profile. Name: {data.get('name', 'N/A')}, "
                        f"Email: {data.get('email', 'hidden')}, "
                        f"Location: {data.get('location', 'N/A')}, "
                        f"Public repos: {data.get('public_repos', 0)}"
                    ),
                    "raw_data": {
                        "login": data.get("login"),
                        "name": data.get("name"),
                        "email": data.get("email"),
                        "location": data.get("location"),
                        "public_repos": data.get("public_repos"),
                        "followers": data.get("followers"),
                    },
                }
            except Exception:
                return {"found": False}

    async def _check_reddit(self, username: str) -> Dict[str, Any]:
        """Check if a Reddit profile is publicly accessible."""
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                headers = {"User-Agent": "DataShield-OSINT/1.0"}
                resp = await client.get(
                    f"https://www.reddit.com/user/{quote(username)}/about.json",
                    headers=headers,
                )
                if resp.status_code != 200:
                    return {"found": False}

                data = resp.json().get("data", {})
                if data.get("is_suspended"):
                    return {"found": False}

                return {
                    "found": True,
                    "platform": "Reddit",
                    "finding_type": "social_media",
                    "source_url": f"https://reddit.com/user/{username}",
                    "source_domain": "reddit.com",
                    "source_title": f"Reddit Profile: u/{username}",
                    "source_name": "Reddit",
                    "severity": "low",
                    "risk_score": 2.5,
                    "exposed_data_types": ["username", "post_history"],
                    "reputation_risk": True,
                    "snippet": (
                        f"Public Reddit account. "
                        f"Created: {data.get('created_utc', 'N/A')}, "
                        f"Karma: {data.get('total_karma', 0)}"
                    ),
                }
            except Exception:
                return {"found": False}

    async def _check_twitter_public(self, username: str) -> Dict[str, Any]:
        """Check Twitter public profile availability (no API key required for existence check)."""
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                resp = await client.head(
                    f"https://twitter.com/{quote(username)}",
                    headers={"User-Agent": "Mozilla/5.0 (compatible; DataShield-OSINT/1.0)"},
                )
                if resp.status_code == 200:
                    return {
                        "found": True,
                        "platform": "X (Twitter)",
                        "finding_type": "social_media",
                        "source_url": f"https://twitter.com/{username}",
                        "source_domain": "twitter.com",
                        "source_title": f"X/Twitter Profile: @{username}",
                        "source_name": "X (Twitter)",
                        "severity": "medium",
                        "risk_score": 4.0,
                        "exposed_data_types": ["username", "posts"],
                        "reputation_risk": True,
                        "snippet": f"Public X/Twitter profile found for username @{username}.",
                    }
                return {"found": False}
            except Exception:
                return {"found": False}
