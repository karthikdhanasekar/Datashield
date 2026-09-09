"""
DataShield OSINT - Maigret Adapter
-------------------------------------
Wraps the open-source 'maigret' library to check a username across
3,000+ social platforms and websites.

Maigret is a Sherlock fork that:
  - Checks 3000+ sites (vs Sherlock's ~400)
  - Extracts profile metadata (bio, location, followers)
  - Follows cross-platform links for recursive discovery
  - Outputs JSON/HTML/PDF reports
  - Requires NO API keys

Install: pip install maigret==0.4.5
GitHub:  https://github.com/soxoj/maigret
License: MIT
"""
import asyncio
import json
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any

import structlog

logger = structlog.get_logger(__name__)

# Sites known to expose sensitive personal data — get higher severity
HIGH_RISK_SITES = {
    "github", "gitlab", "linkedin", "facebook", "instagram",
    "twitter", "keybase", "pastebin", "reddit", "discord",
    "telegram", "medium", "gravatar", "hackerrank", "stackoverflow",
}


async def check_username_maigret(username: str, top_sites: int = 100) -> List[Dict[str, Any]]:
    """
    Run maigret on 'username' across 3000+ sites.

    Uses maigret's CLI via subprocess and parses JSON output.
    Runs in a thread pool to avoid blocking the event loop.

    Args:
        username: The username to investigate
        top_sites: Limit scan to top N sites (lower = faster; max useful = 500)

    Returns:
        List of DataShield finding dicts for each site where username was found.
    """
    username = username.strip().lower()
    if not username or len(username) < 2:
        return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_maigret_sync, username, top_sites)


def _run_maigret_sync(username: str, top_sites: int) -> List[Dict[str, Any]]:
    """
    Blocking implementation — call maigret CLI and parse JSON output.
    Called from run_in_executor so it doesn't block the event loop.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            sys.executable, "-m", "maigret",
            username,
            "-J", "simple",              # JSON output format
            "--top-sites", str(top_sites),
            "--timeout", "10",
            "--no-color",
            "--retries", "1",
            "--folderoutput", tmpdir,    # all reports go here
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,   # 3 min hard limit
                cwd=tmpdir,
            )

            # Maigret names the file: report_<username>_simple.json
            # Search the tmpdir for any matching JSON file
            candidates = list(Path(tmpdir).glob(f"*{username}*simple*.json"))
            if not candidates:
                # Try any JSON file in the output dir
                candidates = list(Path(tmpdir).glob("*.json"))

            if not candidates:
                logger.warning("maigret JSON output not found", tmpdir=tmpdir)
                return _demo_results(username)

            json_path = candidates[0]
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            return _parse_maigret_json(raw, username)

        except subprocess.TimeoutExpired:
            logger.warning("maigret timed out", username=username)
            return []
        except FileNotFoundError:
            logger.warning("maigret not installed — run: pip install maigret")
            return _demo_results(username)
        except Exception as e:
            logger.error("maigret failed", error=str(e), username=username)
            return _demo_results(username)


def _parse_maigret_json(raw: Dict, username: str) -> List[Dict[str, Any]]:
    """
    Parse maigret's JSON output into DataShield findings.

    Maigret v0.6+ simple JSON structure:
    {
      "Instagram": {
        "status": { "status": "Claimed", "url": "...", "site_name": "..." },
        "url_user": "https://www.instagram.com/username/",
        "url_main": "https://www.instagram.com/",
        "rank": 4
      },
      "GitHub": { ... }
    }
    """
    findings = []
    # simple format: top-level keys are site names
    for site_name, site_info in raw.items():
        if not isinstance(site_info, dict):
            continue

        status_obj = site_info.get("status", {})
        # v0.6+ uses "Claimed"/"Available"/"Unknown"
        status_str = status_obj.get("status", "") if isinstance(status_obj, dict) else str(status_obj)

        if status_str.lower() not in ("claimed", "found"):
            continue

        url    = site_info.get("url_user") or status_obj.get("url", "")
        tags   = site_info.get("site", {}).get("tags", []) if isinstance(site_info.get("site"), dict) else []
        info   = status_obj.get("ids", {}) or {}
        domain = _extract_domain(url)
        rank   = site_info.get("rank", 9999)

        # Higher severity for more popular / sensitive sites
        is_high_risk = rank <= 200 or any(s in site_name.lower() for s in HIGH_RISK_SITES)
        has_info     = bool(info)

        if is_high_risk and has_info:
            severity, risk_score = "high", 7.5
        elif is_high_risk:
            severity, risk_score = "high", 6.5
        elif has_info:
            severity, risk_score = "medium", 5.0
        else:
            severity, risk_score = "medium", 4.0

        exposed = ["username"]
        for k, v in info.items():
            if v:
                key_lower = k.lower()
                if "name" in key_lower:
                    exposed.append("full_name")
                elif "email" in key_lower:
                    exposed.append("email")
                elif "location" in key_lower or "city" in key_lower:
                    exposed.append("location")
                elif "bio" in key_lower:
                    exposed.append("bio")

        snippet_parts = [f"Profile at {url}"]
        if tags:
            snippet_parts.append(f"Tags: {', '.join(tags[:3])}")
        if rank < 9999:
            snippet_parts.append(f"Alexa rank: {rank}")

        findings.append({
            "finding_type":           "social_media",
            "source_name":            f"Maigret – {site_name}",
            "source_url":             url,
            "source_domain":          domain,
            "source_title":           f"{site_name} profile: {username}",
            "severity":               severity,
            "risk_score":             risk_score,
            "description": (
                f"Username '{username}' found on {site_name} via Maigret. "
                f"Profile is publicly accessible. "
                f"Exposed: {', '.join(exposed)}."
            ),
            "exposed_data_types":     exposed,
            "reputation_risk":        True,
            "identity_theft_risk":    severity == "high",
            "financial_risk":         False,
            "credential_exposure":    False,
            "government_id_exposure": False,
            "snippet":                " | ".join(snippet_parts),
            "raw_data": {
                "site":     site_name,
                "url":      url,
                "tags":     tags,
                "status":   status_str,
                "rank":     rank,
                "ids":      info,
                "source":   "Maigret",
            },
        })

    logger.info("maigret scan complete", username=username, found=len(findings))
    return findings


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url


def _demo_results(username: str) -> List[Dict[str, Any]]:
    """Demo results when maigret is not installed."""
    return [
        {
            "finding_type": "social_media",
            "source_name": "Maigret (demo) – GitHub",
            "source_url": f"https://github.com/{username}",
            "source_domain": "github.com",
            "source_title": f"GitHub profile check for '{username}'",
            "severity": "medium",
            "risk_score": 3.5,
            "description": (
                "Demo result: maigret library not installed. "
                "Install with: pip install maigret — then re-run scan."
            ),
            "exposed_data_types": ["username"],
            "reputation_risk": True,
            "identity_theft_risk": False,
            "credential_exposure": False,
            "snippet": "Demo mode — install maigret for real results across 3000+ sites",
            "raw_data": {"demo": True},
        }
    ]
