"""
DataShield OSINT - Sherlock Adapter
=====================================
Wraps the open-source 'sherlock-project' tool to hunt usernames
across 400+ social networks.

Package name:    sherlock-project  (pip install sherlock-project)
Module name:     sherlock_project  (python -m sherlock_project)
GitHub:          https://github.com/sherlock-project/sherlock
License:         MIT
"""
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)

HIGH_RISK_SITES = {
    "github", "gitlab", "linkedin", "twitter", "instagram",
    "facebook", "keybase", "pastebin", "reddit", "discord",
    "telegram", "stackoverflow", "hackerrank", "gravatar",
}


async def check_username_sherlock(
    username: str,
    timeout_per_site: int = 10,
) -> List[Dict[str, Any]]:
    """
    Run Sherlock on a username and return DataShield findings.
    Uses python -m sherlock_project (installed as sherlock-project package).
    """
    username = username.strip().lower()
    if not username or len(username) < 2:
        return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _run_sherlock_sync, username, timeout_per_site
    )


def _run_sherlock_sync(username: str, timeout_per_site: int) -> List[Dict[str, Any]]:
    """Blocking — runs sherlock_project CLI, parses stdout."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / f"{username}.txt"

        cmd = [
            sys.executable, "-m", "sherlock_project",
            username,
            "--output", str(output_file),
            "--timeout", str(timeout_per_site),
            "--print-found",
            "--no-color",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=tmpdir,
            )
            return _parse_sherlock_output(result.stdout, username)

        except subprocess.TimeoutExpired:
            logger.warning("Sherlock timed out", username=username)
            return []
        except FileNotFoundError:
            logger.warning("sherlock_project not installed — pip install sherlock-project")
            return _demo_results(username)
        except Exception as e:
            logger.error("Sherlock failed", error=str(e), username=username)
            return []


def _parse_sherlock_output(stdout: str, username: str) -> List[Dict[str, Any]]:
    findings = []
    seen_urls: set = set()

    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("[+]"):
            continue
        try:
            content  = line[4:].strip()
            if ": " not in content:
                continue
            site_name, url = content.split(": ", 1)
            site_name = site_name.strip()
            url       = url.strip()
        except ValueError:
            continue

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        domain      = _domain_from_url(url)
        site_lower  = site_name.lower()
        is_high_risk = any(s in site_lower for s in HIGH_RISK_SITES)
        severity    = "high"   if is_high_risk else "medium"
        risk_score  = 6.5 if is_high_risk else 4.0

        findings.append({
            "finding_type":           "social_media",
            "source_name":            f"Sherlock – {site_name}",
            "source_url":             url,
            "source_domain":          domain,
            "source_title":           f"{site_name} account: @{username}",
            "severity":               severity,
            "risk_score":             risk_score,
            "description": (
                f"Username '{username}' found on {site_name} via Sherlock. "
                f"Profile at {url} may expose personal information."
            ),
            "exposed_data_types":     ["username", "profile"],
            "reputation_risk":        True,
            "identity_theft_risk":    is_high_risk,
            "financial_risk":         False,
            "credential_exposure":    False,
            "government_id_exposure": False,
            "snippet":                f"Active {site_name} account found: {url}",
            "raw_data": {
                "site":     site_name,
                "url":      url,
                "username": username,
                "source":   "Sherlock",
            },
        })

    logger.info("Sherlock scan complete", username=username, found=len(findings))
    return findings


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url


def _demo_results(username: str) -> List[Dict[str, Any]]:
    return [{
        "finding_type":           "social_media",
        "source_name":            "Sherlock (not installed)",
        "source_url":             f"https://github.com/{username}",
        "source_domain":          "github.com",
        "source_title":           f"Sherlock username scan: {username}",
        "severity":               "low",
        "risk_score":             1.0,
        "description":            "sherlock-project not installed — pip install sherlock-project",
        "exposed_data_types":     ["username"],
        "reputation_risk":        False,
        "identity_theft_risk":    False,
        "financial_risk":         False,
        "credential_exposure":    False,
        "government_id_exposure": False,
        "snippet":                "Demo mode",
        "raw_data":               {"demo": True, "tool": "sherlock"},
    }]
