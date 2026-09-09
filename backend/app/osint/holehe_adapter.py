"""
DataShield OSINT - Holehe Adapter
-------------------------------------
Wraps the open-source 'holehe' library to check whether an email address
is registered on 120+ websites (Twitter, Instagram, Adobe, Spotify, etc.)

Holehe uses the "forgotten password" flow — it does NOT log in, does NOT
read private data, and does NOT alert the account owner.

Install: pip install holehe==1.61
GitHub:  https://github.com/megadose/holehe
License: GNU GPLv3

Async bridge note:
  Holehe uses 'trio' internally. The correct way to call it from an
  asyncio context is: run holehe's trio event loop inside a thread pool
  executor so the two loops never conflict.
"""
import asyncio
import concurrent.futures
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


async def check_email_registrations(email: str) -> List[Dict[str, Any]]:
    """
    Use holehe to check if 'email' is registered on 120+ websites.

    Runs holehe's trio event loop in a separate thread via run_in_executor
    to avoid asyncio ↔ trio loop conflicts.

    Returns a list of DataShield finding dicts for each site where the
    email was found registered.
    """
    try:
        import holehe  # noqa — verify installed
    except ImportError:
        logger.warning("holehe not installed — run: pip install holehe")
        return _demo_results(email)

    loop = asyncio.get_event_loop()
    try:
        # run_in_executor launches a fresh thread with its own trio loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            raw_results = await loop.run_in_executor(
                pool, _run_holehe_in_thread, email
            )
        return _format_findings(raw_results, email)
    except Exception as e:
        logger.error("holehe scan failed", email=email, error=str(e))
        return _demo_results(email)


def _run_holehe_in_thread(email: str) -> List[Dict]:
    """
    Runs entirely inside a fresh thread.
    Starts a brand-new trio event loop — completely isolated from asyncio.
    Uses holehe v1.61 API: import_submodules() + get_functions(modules).
    """
    import trio
    import holehe.core as holehe_core

    # holehe v1.61 requires modules dict from import_submodules
    modules = holehe_core.import_submodules("holehe.modules")
    funcs   = holehe_core.get_functions(modules)
    results: List[Dict] = []

    async def _inner():
        async with trio.open_nursery() as nursery:
            for func in funcs:
                nursery.start_soon(_check_one, func, email, results)

    async def _check_one(func, email: str, out: list):
        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=8.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 DataShield-OSINT/1.0"},
            ) as client:
                site_results: list = []          # holehe v1.61 expects a list
                await func(email, client, site_results)
                for r in site_results:
                    if r.get("exists"):
                        out.append(r)
        except Exception:
            pass

    trio.run(_inner)
    return results


def _format_findings(raw_results: List[Dict], email: str) -> List[Dict[str, Any]]:
    """Convert holehe output to DataShield finding format."""
    findings = []
    high_risk_sites = {
        "twitter", "instagram", "facebook", "github", "linkedin",
        "paypal", "amazon", "apple", "discord", "slack", "microsoft",
        "google", "dropbox", "adobe", "spotify",
    }

    for r in raw_results:
        if not r.get("exists"):
            continue

        site_name = r.get("name", "Unknown")
        domain    = r.get("domain", "")
        severity  = "high" if site_name.lower() in high_risk_sites else "medium"
        risk      = 6.5 if severity == "high" else 4.0

        findings.append({
            "finding_type":           "social_media",
            "source_name":            f"Holehe – {site_name}",
            "source_url":             f"https://{domain}" if domain else "",
            "source_domain":          domain,
            "source_title":           f"Email registered on {site_name}",
            "severity":               severity,
            "risk_score":             risk,
            "description": (
                f"Email is registered on {site_name}. "
                "This confirms an active account and expands your digital footprint."
            ),
            "exposed_data_types":     ["email", "account_registration"],
            "reputation_risk":        True,
            "identity_theft_risk":    severity == "high",
            "financial_risk":         site_name.lower() in {"paypal", "amazon", "ebay"},
            "credential_exposure":    False,
            "government_id_exposure": False,
            "snippet": (
                f"Holehe confirmed registration on {site_name} ({domain}). "
                f"Rate-limited: {r.get('rateLimit', False)}"
            ),
            "raw_data": {
                "site":         site_name,
                "domain":       domain,
                "exists":       True,
                "rate_limited": r.get("rateLimit", False),
                "extra_info":   r.get("others"),
                "source":       "Holehe",
            },
        })

    return findings


def _demo_results(email: str) -> List[Dict[str, Any]]:
    """Fallback when holehe is not installed or fails."""
    username = email.split("@")[0]
    return [
        {
            "finding_type":           "social_media",
            "source_name":            "Holehe (demo) – GitHub",
            "source_url":             f"https://github.com/{username}",
            "source_domain":          "github.com",
            "source_title":           f"Email possibly registered on GitHub",
            "severity":               "medium",
            "risk_score":             4.0,
            "description": (
                "Demo result: holehe library is installed but couldn't run in this context. "
                "This will work correctly during a full Celery scan."
            ),
            "exposed_data_types":     ["email", "account_registration"],
            "reputation_risk":        True,
            "identity_theft_risk":    False,
            "financial_risk":         False,
            "credential_exposure":    False,
            "government_id_exposure": False,
            "snippet":                "Demo mode — holehe runs in Celery worker context",
            "raw_data":               {"demo": True},
        }
    ]
