"""
DataShield OSINT - Master OSINT Engine
========================================
Central orchestrator that calls all OSINT tool adapters based on
scan type and requested modules.

Tool routing:
  email     → holehe + HIBP breach + paste sites + search engine + social
              + linkedin (dork) + instagram + dark web indicators
  username  → maigret + username_osint (sherlock-style) + paste
              + instagram + linkedin + dark web
  phone     → phone_osint (phonenumbers) + paste + search engine
  name      → theHarvester + search engine + social media
              + linkedin + facebook (dork) + dark web
  address   → search engine
  domain    → theHarvester + shodan + search engine

All tools are open-source, ethical, and public-data-only.
"""
import asyncio
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


async def run_full_osint(
    query_value: str,
    scan_type: str,
    modules: List[str],
    progress_callback=None,
) -> List[Dict[str, Any]]:
    """
    Main entry point for the OSINT engine.

    Args:
        query_value:       The data to search for (email, username, phone, etc.)
        scan_type:         One of: email, username, phone, name, address,
                           aadhaar, pan, passport, social_profile, full
        modules:           Subset of modules to run (or all if empty)
        progress_callback: Optional async fn(pct: int) called during scan

    Returns:
        Deduplicated list of DataShield finding dicts.
    """
    all_findings: List[Dict[str, Any]] = []
    tasks = _build_task_list(query_value, scan_type, modules)
    total = len(tasks)

    if not tasks:
        logger.warning("No OSINT tasks matched", scan_type=scan_type, modules=modules)
        return []

    logger.info("OSINT engine starting", scan_type=scan_type, tasks=total)

    for i, (task_name, coro) in enumerate(tasks):
        try:
            logger.info(f"Running: {task_name}")
            results = await coro
            if isinstance(results, list):
                all_findings.extend(results)
                logger.info(f"{task_name} → {len(results)} findings")
        except Exception as e:
            logger.error(f"{task_name} failed", error=str(e))

        if progress_callback:
            pct = int(((i + 1) / total) * 90)
            await progress_callback(pct)

    # Deduplicate by source URL
    deduped = _deduplicate(all_findings)
    logger.info("OSINT engine complete", total_findings=len(deduped))
    return deduped


def _build_task_list(
    query: str, scan_type: str, modules: List[str]
) -> List[tuple]:
    """
    Build the ordered list of (name, coroutine) tuples to run.
    Each coroutine returns List[Dict[str, Any]].
    """
    tasks = []
    want = set(modules) if modules else _all_modules()

    # ── EMAIL scans ───────────────────────────────────────────────────────────
    if scan_type == "email":
        if "breach" in want:
            from app.osint.breach_monitor import BreachMonitor
            monitor = BreachMonitor()
            tasks.append(("HIBP Breach Check", _hibp_task(monitor, query)))

        if "holehe" in want or "social_media" in want:
            from app.osint.holehe_adapter import check_email_registrations
            tasks.append(("Holehe Email Registration", check_email_registrations(query)))

        if "paste" in want or "search_engine" in want:
            from app.osint.pastebin_scraper import search_pastes
            tasks.append(("Paste Site Scan", search_pastes(query, scan_type)))

        if "search_engine" in want:
            from app.osint.search_engine import SearchEngineScanner
            scanner = SearchEngineScanner()
            tasks.append(("Search Engine Scan", _search_engine_task(scanner, query, scan_type)))

        if "social_media" in want:
            from app.osint.social_media import SocialMediaScanner
            social = SocialMediaScanner()
            tasks.append(("Social Media Scan", social.check_email_social(query)))

        if "document" in want:
            from app.osint.document_scanner import DocumentScanner
            doc = DocumentScanner()
            tasks.append(("Document Scanner", doc.search_document_exposure(query, scan_type)))

        # ── New: LinkedIn / Instagram / Dark Web ─────────────────────────────
        if "linkedin" in want or "social_media" in want:
            from app.osint.linkedin_osint import check_linkedin_exposure
            tasks.append(("LinkedIn OSINT", check_linkedin_exposure(query, scan_type)))

        if "instagram" in want or "social_media" in want:
            username_part = query.split("@")[0]
            from app.osint.instagram_osint import check_instagram_exposure
            tasks.append(("Instagram OSINT", check_instagram_exposure(username_part)))

        if "darkweb" in want or "breach" in want:
            from app.osint.darkweb_osint import check_dark_web_exposure
            tasks.append(("Dark Web Indicators", check_dark_web_exposure(query, scan_type)))

        # ── New: SpiderFoot email modules (LeakIX + Hunter.io) ────────────────
        if "spiderfoot" in want or "breach" in want:
            from app.osint.spiderfoot_adapter import run_spiderfoot_scan
            tasks.append(("SpiderFoot Email Scan", run_spiderfoot_scan(query, scan_type)))

        # ── Maigret + Sherlock on username derived from email ─────────────────
        # These search 3000+ / 400+ sites for the username part of the email
        if "maigret" in want or "social_media" in want:
            username_part = query.split("@")[0]
            from app.osint.maigret_adapter import check_username_maigret
            tasks.append(("Maigret Username (3000+ sites)",
                          check_username_maigret(username_part, top_sites=100)))

        if "sherlock" in want or "social_media" in want:
            username_part = query.split("@")[0]
            from app.osint.sherlock_adapter import check_username_sherlock
            tasks.append(("Sherlock (400+ sites)",
                          check_username_sherlock(username_part, timeout_per_site=10)))

    # ── USERNAME scans ────────────────────────────────────────────────────────
    elif scan_type == "username":
        if "maigret" in want or "social_media" in want:
            from app.osint.maigret_adapter import check_username_maigret
            tasks.append(("Maigret Username (3000+ sites)", check_username_maigret(query, top_sites=150)))

        if "social_media" in want:
            from app.osint.social_media import SocialMediaScanner
            social = SocialMediaScanner()
            tasks.append(("Social Media Platforms", social.check_username_platforms(query)))

        if "paste" in want or "search_engine" in want:
            from app.osint.pastebin_scraper import search_pastes
            tasks.append(("Paste Site Scan", search_pastes(query, scan_type)))

        if "search_engine" in want:
            from app.osint.search_engine import SearchEngineScanner
            scanner = SearchEngineScanner()
            tasks.append(("Search Engine Scan", _search_engine_task(scanner, query, scan_type)))

        # ── New: LinkedIn / Instagram / Dark Web ─────────────────────────────
        if "linkedin" in want or "social_media" in want:
            from app.osint.linkedin_osint import check_linkedin_exposure
            tasks.append(("LinkedIn OSINT", check_linkedin_exposure(query, scan_type)))

        if "instagram" in want or "social_media" in want:
            from app.osint.instagram_osint import check_instagram_exposure
            tasks.append(("Instagram OSINT", check_instagram_exposure(query)))

        if "darkweb" in want or "breach" in want:
            from app.osint.darkweb_osint import check_dark_web_exposure
            tasks.append(("Dark Web Indicators", check_dark_web_exposure(query, scan_type)))

        # ── New: Sherlock + Social-Analyzer username scan ─────────────────────
        if "sherlock" in want or "social_media" in want:
            from app.osint.sherlock_adapter import check_username_sherlock
            tasks.append(("Sherlock (400+ sites)", check_username_sherlock(query)))

        if "social_analyzer" in want or "social_media" in want:
            from app.osint.social_analyzer_adapter import check_username_social_analyzer
            tasks.append(("Social-Analyzer (300+ sites)", check_username_social_analyzer(query)))

        # ── New: SpiderFoot username modules ──────────────────────────────────
        if "spiderfoot" in want or "social_media" in want:
            from app.osint.spiderfoot_adapter import run_spiderfoot_scan
            tasks.append(("SpiderFoot Username Scan", run_spiderfoot_scan(query, scan_type)))

    # ── PHONE scans ───────────────────────────────────────────────────────────
    elif scan_type == "phone":
        if "phone" in want or "search_engine" in want:
            from app.osint.phone_osint import analyze_phone_number
            tasks.append(("Phone Number OSINT", analyze_phone_number(query)))

        if "paste" in want or "search_engine" in want:
            from app.osint.pastebin_scraper import search_pastes
            tasks.append(("Paste Site Scan", search_pastes(query, scan_type)))

        if "search_engine" in want:
            from app.osint.search_engine import SearchEngineScanner
            scanner = SearchEngineScanner()
            tasks.append(("Search Engine Scan", _search_engine_task(scanner, query, scan_type)))

    # ── NAME scans ────────────────────────────────────────────────────────────
    elif scan_type == "name":
        if "search_engine" in want:
            from app.osint.search_engine import SearchEngineScanner
            scanner = SearchEngineScanner()
            tasks.append(("Search Engine Scan", _search_engine_task(scanner, query, scan_type)))

        if "document" in want:
            from app.osint.document_scanner import DocumentScanner
            doc = DocumentScanner()
            tasks.append(("Document Scanner", doc.search_document_exposure(query, scan_type)))

        if "social_media" in want:
            from app.osint.maigret_adapter import check_username_maigret
            # Use first name as username attempt
            username_attempt = query.lower().replace(" ", "")
            tasks.append(("Maigret Username Attempt", check_username_maigret(username_attempt, top_sites=50)))

        # ── New: LinkedIn / Facebook / Dark Web ──────────────────────────────
        if "linkedin" in want or "social_media" in want:
            from app.osint.linkedin_osint import check_linkedin_exposure
            tasks.append(("LinkedIn OSINT", check_linkedin_exposure(query, scan_type)))

        if "facebook" in want or "social_media" in want:
            from app.osint.instagram_osint import check_facebook_exposure
            tasks.append(("Facebook OSINT", check_facebook_exposure(query, scan_type)))

        if "darkweb" in want or "breach" in want:
            from app.osint.darkweb_osint import check_dark_web_exposure
            tasks.append(("Dark Web Indicators", check_dark_web_exposure(query, scan_type)))

        # ── New: Sherlock + Social-Analyzer name-derived username ─────────────
        if "sherlock" in want or "social_media" in want:
            username_attempt = query.lower().replace(" ", "")
            from app.osint.sherlock_adapter import check_username_sherlock
            tasks.append(("Sherlock Username Attempt", check_username_sherlock(username_attempt)))

        if "social_analyzer" in want or "social_media" in want:
            username_attempt = query.lower().replace(" ", "")
            from app.osint.social_analyzer_adapter import check_username_social_analyzer
            tasks.append(("Social-Analyzer", check_username_social_analyzer(username_attempt)))

    # ── ADDRESS scans ─────────────────────────────────────────────────────────
    elif scan_type == "address":
        if "search_engine" in want:
            from app.osint.search_engine import SearchEngineScanner
            scanner = SearchEngineScanner()
            tasks.append(("Search Engine Scan", _search_engine_task(scanner, query, scan_type)))

        if "document" in want:
            from app.osint.document_scanner import DocumentScanner
            doc = DocumentScanner()
            tasks.append(("Document Scanner", doc.search_document_exposure(query, scan_type)))

    # ── GOVERNMENT ID scans (Aadhaar, PAN, Passport) ─────────────────────────
    elif scan_type in ("aadhaar", "pan", "passport"):
        # For government IDs, only search engine + paste (masked)
        if "search_engine" in want:
            from app.osint.search_engine import SearchEngineScanner
            scanner = SearchEngineScanner()
            tasks.append(("Search Engine Scan", _search_engine_task(scanner, query, scan_type)))

        if "paste" in want or "search_engine" in want:
            from app.osint.pastebin_scraper import search_pastes
            tasks.append(("Paste Site Scan", search_pastes(query, scan_type)))

    # ── FULL scan (all modules, all types) ────────────────────────────────────
    elif scan_type == "full":
        # Treat as email if looks like email, else username
        if "@" in query:
            return _build_task_list(query, "email", list(_all_modules()))
        else:
            return _build_task_list(query, "username", list(_all_modules()))

    # ── SOCIAL_PROFILE ────────────────────────────────────────────────────────
    elif scan_type == "social_profile":
        if "social_media" in want:
            from app.osint.maigret_adapter import check_username_maigret
            tasks.append(("Maigret Username", check_username_maigret(query, top_sites=200)))

        if "search_engine" in want:
            from app.osint.search_engine import SearchEngineScanner
            scanner = SearchEngineScanner()
            tasks.append(("Search Engine Scan", _search_engine_task(scanner, query, scan_type)))

    return tasks


async def _hibp_task(monitor, email: str) -> List[Dict]:
    """Run HIBP breach + paste check and format results."""
    breaches = await monitor.check_email_breaches(email)
    pastes = await monitor.get_pastes(email)
    findings = []
    if breaches:
        findings.extend(monitor.format_findings(breaches, email))
    for p in pastes:
        findings.append({
            "finding_type": "paste_site",
            "source_name": f"HIBP Paste – {p.get('Source', 'Unknown')}",
            "source_url": f"https://pastebin.com/{p.get('Id', '')}",
            "source_domain": p.get("Source", "pastebin.com"),
            "source_title": p.get("Title") or "Email found in paste",
            "severity": "critical",
            "risk_score": 9.0,
            "description": (
                f"Email found in public paste on {p.get('Source')}. "
                f"Date: {p.get('Date', 'unknown')}."
            ),
            "exposed_data_types": ["email"],
            "identity_theft_risk": True,
            "reputation_risk": True,
            "credential_exposure": False,
            "snippet": f"Paste source: {p.get('Source')} | Date: {p.get('Date')}",
            "raw_data": p,
        })
    return findings


async def _search_engine_task(scanner, query: str, scan_type: str) -> List[Dict]:
    """Run search engine scan across Google + Bing."""
    all_results = []
    queries = scanner.build_queries(query, scan_type)
    for q in queries[:3]:
        google = await scanner.search_google(q)
        findings = scanner.filter_and_classify(google, query)
        all_results.extend(findings)

        bing = await scanner.search_bing(q)
        bing_findings = scanner.filter_and_classify(bing, query)
        all_results.extend(bing_findings)

        await asyncio.sleep(0.3)  # gentle rate limiting

    return all_results


def _deduplicate(findings: List[Dict]) -> List[Dict]:
    """Remove duplicate findings by source_url; keep highest risk_score."""
    seen: Dict[str, Dict] = {}
    for f in findings:
        key = f.get("source_url") or f.get("source_domain") or f.get("source_name", "")
        if not key:
            findings_no_key = seen.setdefault("__no_key__", None)
            continue
        existing = seen.get(key)
        if existing is None or f.get("risk_score", 0) > existing.get("risk_score", 0):
            seen[key] = f

    return [v for v in seen.values() if v is not None]


def _all_modules() -> set:
    return {
        "breach", "holehe", "maigret", "social_media",
        "search_engine", "document", "paste", "phone",
        "shodan", "linkedin", "instagram", "facebook", "darkweb",
        "sherlock", "social_analyzer", "spiderfoot",
    }
