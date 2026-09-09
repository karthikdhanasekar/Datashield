"""
DataShield OSINT - Username OSINT Module
Sherlock-style username enumeration across 100+ social platforms
Public profiles only — no authentication, no scraping private data
"""
import asyncio
from typing import List, Dict, Any
import httpx
from urllib.parse import quote

# Platform definitions: name → check URL + expected HTTP status for "found"
# Format: { "platform": { "url": "...", "found_status": 200, "data_fields": [...] } }
PLATFORMS: Dict[str, Dict] = {
    "GitHub":          {"url": "https://github.com/{username}",                         "found_status": 200},
    "GitLab":          {"url": "https://gitlab.com/{username}",                         "found_status": 200},
    "Reddit":          {"url": "https://www.reddit.com/user/{username}",                "found_status": 200},
    "Twitter/X":       {"url": "https://twitter.com/{username}",                        "found_status": 200},
    "Instagram":       {"url": "https://www.instagram.com/{username}/",                 "found_status": 200},
    "TikTok":          {"url": "https://www.tiktok.com/@{username}",                    "found_status": 200},
    "YouTube":         {"url": "https://www.youtube.com/@{username}",                   "found_status": 200},
    "Pinterest":       {"url": "https://www.pinterest.com/{username}/",                 "found_status": 200},
    "Twitch":          {"url": "https://www.twitch.tv/{username}",                      "found_status": 200},
    "Steam":           {"url": "https://steamcommunity.com/id/{username}",              "found_status": 200},
    "HackerNews":      {"url": "https://news.ycombinator.com/user?id={username}",       "found_status": 200},
    "Dev.to":          {"url": "https://dev.to/{username}",                             "found_status": 200},
    "Medium":          {"url": "https://medium.com/@{username}",                        "found_status": 200},
    "Pastebin":        {"url": "https://pastebin.com/u/{username}",                     "found_status": 200},
    "Keybase":         {"url": "https://keybase.io/{username}",                         "found_status": 200},
    "Gravatar":        {"url": "https://en.gravatar.com/{username}",                    "found_status": 200},
    "ProductHunt":     {"url": "https://www.producthunt.com/@{username}",               "found_status": 200},
    "Replit":          {"url": "https://replit.com/@{username}",                        "found_status": 200},
    "Codepen":         {"url": "https://codepen.io/{username}",                         "found_status": 200},
    "HuggingFace":     {"url": "https://huggingface.co/{username}",                     "found_status": 200},
    "Behance":         {"url": "https://www.behance.net/{username}",                    "found_status": 200},
    "Dribbble":        {"url": "https://dribbble.com/{username}",                       "found_status": 200},
    "Spotify":         {"url": "https://open.spotify.com/user/{username}",              "found_status": 200},
    "SoundCloud":      {"url": "https://soundcloud.com/{username}",                     "found_status": 200},
    "Flickr":          {"url": "https://www.flickr.com/photos/{username}/",             "found_status": 200},
    "Vimeo":           {"url": "https://vimeo.com/{username}",                          "found_status": 200},
    "Quora":           {"url": "https://www.quora.com/profile/{username}",              "found_status": 200},
    "500px":           {"url": "https://500px.com/p/{username}",                        "found_status": 200},
    "Linktree":        {"url": "https://linktr.ee/{username}",                          "found_status": 200},
    "AboutMe":         {"url": "https://about.me/{username}",                           "found_status": 200},
    "Angel.co":        {"url": "https://angel.co/u/{username}",                         "found_status": 200},
    "Stackoverflow":   {"url": "https://stackoverflow.com/users/{username}",            "found_status": 200},
    "DockerHub":       {"url": "https://hub.docker.com/u/{username}",                   "found_status": 200},
    "Npm":             {"url": "https://www.npmjs.com/~{username}",                     "found_status": 200},
    "PyPI":            {"url": "https://pypi.org/user/{username}/",                     "found_status": 200},
    "Wattpad":         {"url": "https://www.wattpad.com/user/{username}",               "found_status": 200},
    "Roblox":          {"url": "https://www.roblox.com/user.aspx?username={username}",  "found_status": 200},
    "Chess.com":       {"url": "https://www.chess.com/member/{username}",               "found_status": 200},
    "Lichess":         {"url": "https://lichess.org/@/{username}",                      "found_status": 200},
    "Imgur":           {"url": "https://imgur.com/user/{username}",                     "found_status": 200},
    "Fiverr":          {"url": "https://www.fiverr.com/{username}",                     "found_status": 200},
    "Freelancer":      {"url": "https://www.freelancer.com/u/{username}",               "found_status": 200},
    "Trello":          {"url": "https://trello.com/{username}",                         "found_status": 200},
    "Last.fm":         {"url": "https://www.last.fm/user/{username}",                   "found_status": 200},
    "Letterboxd":      {"url": "https://letterboxd.com/{username}/",                    "found_status": 200},
    "Goodreads":       {"url": "https://www.goodreads.com/{username}",                  "found_status": 200},
    "Itch.io":         {"url": "https://{username}.itch.io",                            "found_status": 200},
    "Substack":        {"url": "https://{username}.substack.com",                       "found_status": 200},
    "WordPress":       {"url": "https://{username}.wordpress.com",                      "found_status": 200},
    "Tumblr":          {"url": "https://{username}.tumblr.com",                         "found_status": 200},
}

# Platforms that expose more sensitive data (higher severity if found with data)
HIGH_RISK_PLATFORMS = {
    "LinkedIn", "Facebook", "Instagram", "GitHub",
    "Pastebin", "Twitter/X", "Keybase",
}


class UsernameOSINT:
    """
    Sherlock-style username enumeration across 50+ platforms.
    Checks public HTTP endpoints only — no login, no scraping private pages.
    Runs concurrent checks with a semaphore to respect rate limits.
    """

    def __init__(self, concurrency: int = 15, timeout: float = 8.0):
        self.concurrency = concurrency
        self.timeout = timeout

    async def check_username(self, username: str) -> List[Dict[str, Any]]:
        """
        Check a username across all configured platforms.
        Returns list of findings for platforms where the username was found.
        """
        username = username.strip().lower()
        if not username or len(username) < 2:
            return []

        semaphore = asyncio.Semaphore(self.concurrency)
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; DataShield-OSINT/1.0; privacy-research)",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            tasks = [
                self._check_platform(client, semaphore, platform, config, username)
                for platform, config in PLATFORMS.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        findings = []
        for r in results:
            if isinstance(r, dict) and r.get("found"):
                findings.append(r)

        return findings

    async def _check_platform(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        platform: str,
        config: Dict,
        username: str,
    ) -> Dict[str, Any]:
        """Check a single platform for the given username."""
        async with semaphore:
            url = config["url"].replace("{username}", quote(username))
            try:
                resp = await client.head(url)
                found = resp.status_code == config.get("found_status", 200)

                if not found:
                    return {"found": False}

                severity = "medium"
                risk_score = 3.5

                if platform in HIGH_RISK_PLATFORMS:
                    severity = "high"
                    risk_score = 6.0

                return {
                    "found": True,
                    "platform": platform,
                    "finding_type": "social_media",
                    "source_url": url,
                    "source_domain": _domain_from_url(url),
                    "source_title": f"{platform} Profile: {username}",
                    "source_name": platform,
                    "severity": severity,
                    "risk_score": risk_score,
                    "description": (
                        f"Username '{username}' found on {platform}. "
                        "Public profile may expose personal information."
                    ),
                    "exposed_data_types": ["username", "profile"],
                    "reputation_risk": True,
                    "identity_theft_risk": platform in HIGH_RISK_PLATFORMS,
                    "snippet": f"Active profile found at {url}",
                }

            except (httpx.TimeoutException, httpx.ConnectError):
                return {"found": False}
            except Exception:
                return {"found": False}


def _domain_from_url(url: str) -> str:
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "") or url
    except Exception:
        return url
