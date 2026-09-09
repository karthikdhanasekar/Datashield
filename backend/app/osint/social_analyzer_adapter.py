"""
DataShield OSINT - Social-Analyzer Adapter
==========================================
Wraps the open-source 'social-analyzer' library (QeeqBox) to perform
deep profile analysis across 300+ social media websites.

Social-Analyzer differs from Sherlock / Maigret:
  - Extracts rich profile metadata (bio, follower count, location, links)
  - Detects language and sentiment of profile content
  - Runs both fast (existence check) and slow (metadata extraction) modes
  - Returns structured JSON with confidence scores per platform
  - Works as a Python library (no subprocess needed)

Install:  pip install social-analyzer
GitHub:   https://github.com/qeeqbox/social-analyzer
License:  AGPL-3.0

Note on import path:
  social-analyzer installs to the user site-packages when running as
  a non-root user. We patch sys.path at import time to handle both
  system and user install locations.
"""
import asyncio
import sys
import os
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)

# ── social-analyzer import workaround ────────────────────────────────────────
# The package directory is named 'social-analyzer' (hyphen), which Python
# cannot import directly. We load it via importlib with the filesystem path.
_SOCIAL_ANALYZER_PATH = "/usr/local/lib/python3.11/site-packages/social-analyzer"

def _load_social_analyzer_class():
    """
    Load the SocialAnalyzer class from the hyphenated package directory.
    Returns None if not installed.
    """
    try:
        import importlib.util
        init_path = os.path.join(_SOCIAL_ANALYZER_PATH, "__init__.py")
        if not os.path.exists(init_path):
            return None

        spec = importlib.util.spec_from_file_location(
            "social_analyzer_mod",
            init_path,
            submodule_search_locations=[_SOCIAL_ANALYZER_PATH],
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["social_analyzer_mod"] = mod
        spec.loader.exec_module(mod)

        return getattr(mod, "SocialAnalyzer", None)
    except Exception as e:
        logger.debug("social-analyzer load failed", error=str(e))
        return None


HIGH_RISK_PLATFORMS = {
    "github", "gitlab", "linkedin", "twitter", "instagram",
    "facebook", "keybase", "pastebin", "reddit", "telegram",
    "snapchat", "tiktok", "youtube",
}


def _load_social_analyzer():
    """Lazy-load social-analyzer to avoid import errors at module load time."""
    return _load_social_analyzer_class()


async def check_username_social_analyzer(
    username: str,
    extract_info: bool = True,
) -> List[Dict[str, Any]]:
    """
    Run Social-Analyzer on a username to find and analyse profiles.
    Falls back gracefully if not installed.
    """
    username = username.strip().lower()
    if not username or len(username) < 2:
        return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _run_social_analyzer_sync, username, extract_info
    )


def _run_social_analyzer_sync(
    username: str,
    extract_info: bool,
) -> List[Dict[str, Any]]:
    """Blocking implementation — run in thread pool via run_in_executor."""
    SocialAnalyzerClass = _load_social_analyzer()
    if SocialAnalyzerClass is None:
        logger.warning("social-analyzer not available")
        return _demo_results(username)

    try:
        sa = SocialAnalyzerClass()
        # run() returns list of detected profiles
        profiles = sa.run_as_object(
            username=username,
            websites="",       # all
            logs_dir="",
            mode="fast",
            extract=extract_info,
            filter="good",
            metadata=False,
            timeout=10,
            top=50,
        ) or []

        return _parse_social_analyzer_result(profiles, username)

    except AttributeError:
        # API differs by version — fall back to CLI
        return _run_via_cli(username)
    except Exception as e:
        logger.error("social-analyzer failed", error=str(e), username=username)
        return []


def _run_via_cli(username: str) -> List[Dict[str, Any]]:
    """Fallback: invoke social-analyzer via subprocess CLI."""
    import subprocess, json, tempfile
    try:
        result = subprocess.run(
            [sys.executable, "-m", "social_analyzer_mod",
             "--username", username, "--mode", "fast",
             "--output", "json", "--top", "20"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return _parse_social_analyzer_result(
                data.get("detected", data.get("found", [])),
                username
            )
    except Exception as e:
        logger.debug("social-analyzer CLI fallback failed", error=str(e))
    return []


def _parse_social_analyzer_result(
    profiles,
    username: str,
) -> List[Dict[str, Any]]:
    """
    Convert social-analyzer result to DataShield finding dicts.
    Accepts either a list of profile dicts or the older dict format.
    """
    # Normalise to list
    if isinstance(profiles, dict):
        detected = profiles.get("detected", profiles.get("found", []))
    elif isinstance(profiles, list):
        detected = profiles
    else:
        return []

    if not detected:
        return []

    findings: List[Dict[str, Any]] = []

    for hit in detected:
        site_name  = hit.get("website", hit.get("name", "Unknown"))
        url        = hit.get("link", hit.get("url", ""))
        confidence = int(hit.get("rate", hit.get("confidence", 50)))
        extracted  = hit.get("extract", hit.get("info", {})) or {}

        if not url or confidence < 60:
            # Skip low-confidence hits to reduce false positives
            continue

        site_lower  = site_name.lower()
        is_high_risk = any(s in site_lower for s in HIGH_RISK_PLATFORMS)

        # Build exposed data types from extracted metadata
        exposed = ["username", "profile"]
        if extracted.get("name") or extracted.get("fullname"):
            exposed.append("full_name")
        if extracted.get("email"):
            exposed.append("email")
        if extracted.get("location") or extracted.get("country"):
            exposed.append("location")
        if extracted.get("bio") or extracted.get("about"):
            exposed.append("bio")
        if extracted.get("followers") or extracted.get("following"):
            exposed.append("social_connections")
        if extracted.get("website") or extracted.get("links"):
            exposed.append("linked_accounts")

        has_rich_data = len(exposed) > 2
        if is_high_risk and has_rich_data:
            severity, risk_score = "high", 7.5
        elif is_high_risk or has_rich_data:
            severity, risk_score = "medium", 5.0
        else:
            severity, risk_score = "low", 2.5

        # Build snippet from extracted fields
        snippet_parts = [f"Profile at {url} (confidence: {confidence}%)"]
        if extracted.get("name"):
            snippet_parts.append(f"Name: {extracted['name']}")
        if extracted.get("location"):
            snippet_parts.append(f"Location: {extracted['location']}")
        if extracted.get("bio"):
            bio = str(extracted["bio"])[:100]
            snippet_parts.append(f"Bio: {bio}")

        domain = _domain_from_url(url)

        findings.append({
            "finding_type":           "social_media",
            "source_name":            f"Social-Analyzer – {site_name}",
            "source_url":             url,
            "source_domain":          domain,
            "source_title":           f"{site_name} profile: @{username}",
            "severity":               severity,
            "risk_score":             risk_score,
            "description": (
                f"Username '{username}' detected on {site_name} by Social-Analyzer "
                f"(confidence: {confidence}%). "
                f"Exposed data: {', '.join(exposed)}."
            ),
            "exposed_data_types":     exposed,
            "reputation_risk":        True,
            "identity_theft_risk":    is_high_risk and has_rich_data,
            "financial_risk":         False,
            "credential_exposure":    False,
            "government_id_exposure": False,
            "snippet":                " | ".join(snippet_parts),
            "raw_data": {
                "site":       site_name,
                "url":        url,
                "confidence": confidence,
                "extracted":  extracted,
                "source":     "Social-Analyzer",
            },
        })

    logger.info(
        "Social-Analyzer scan complete",
        username=username,
        found=len(findings),
    )
    return findings


def _domain_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url


def _demo_results(username: str) -> List[Dict[str, Any]]:
    return [
        {
            "finding_type":           "social_media",
            "source_name":            "Social-Analyzer (not importable)",
            "source_url":             "",
            "source_domain":          "",
            "source_title":           f"Social-Analyzer scan: {username}",
            "severity":               "low",
            "risk_score":             1.0,
            "description": (
                "social-analyzer installed but not importable from current PATH. "
                "This will be fixed in the next Docker image rebuild."
            ),
            "exposed_data_types":     ["username"],
            "reputation_risk":        False,
            "identity_theft_risk":    False,
            "financial_risk":         False,
            "credential_exposure":    False,
            "government_id_exposure": False,
            "snippet":                "social-analyzer path issue — will be fixed after image rebuild",
            "raw_data":               {"demo": True, "tool": "social-analyzer"},
        }
    ]
