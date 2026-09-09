"""
DataShield OSINT - Scan Celery Tasks
=========================================
Orchestrates the full OSINT scan pipeline using the master OsintEngine.

Flow:
  1. Celery worker picks up run_osint_scan task
  2. Marks scan RUNNING in DB
  3. Calls osint_engine.run_full_osint() — routes to all real OSINT tools:
       email    → HIBP + Holehe + paste + search + social
       username → Maigret (3000+ sites) + paste + search
       phone    → phonenumbers + directories + paste + search
       name     → theHarvester + search + document
       domain   → theHarvester + Shodan + search
  4. Each finding classified by ExposureClassifier
  5. Findings persisted to PostgreSQL
  6. Exposure score calculated
  7. Notification created if high/critical findings found
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def run_sync(coro):
    """Run an async coroutine from a synchronous Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="app.tasks.scan_tasks.run_osint_scan",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=480,
    time_limit=540,
)
def run_osint_scan(
    self,
    scan_id: str,
    query_value: str,
    scan_type: str,
    modules: List[str],
):
    """
    Main OSINT scan task — entry point from the API.
    Delegates to the async implementation via run_sync().
    """
    return run_sync(_run_scan_async(self, scan_id, query_value, scan_type, modules))


# ── Async implementation ──────────────────────────────────────────────────────

async def _run_scan_async(
    task,
    scan_id: str,
    query_value: str,
    scan_type: str,
    modules: List[str],
):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.scan import ScanRequest, ScanStatus, Finding
    from app.osint.osint_engine import run_full_osint
    from app.osint.exposure_classifier import ExposureClassifier

    async with AsyncSessionLocal() as db:
        # ── 1. Fetch scan record ─────────────────────────────────────────────
        result = await db.execute(select(ScanRequest).where(ScanRequest.id == scan_id))
        scan = result.scalar_one_or_none()
        if not scan:
            logger.error(f"Scan {scan_id} not found in database")
            return

        # ── 2. Mark as RUNNING ───────────────────────────────────────────────
        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        scan.progress = 5
        await db.commit()
        logger.info(f"Scan {scan_id} started | type={scan_type} | modules={modules}")

        classifier = ExposureClassifier()
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        try:
            # ── 3. Progress callback (updates DB during scan) ────────────────
            async def update_progress(pct: int):
                scan.progress = pct
                scan.modules_completed = []  # updated below
                try:
                    await db.commit()
                except Exception:
                    pass

            # ── 4. Run all OSINT tools via master engine ─────────────────────
            raw_findings = await run_full_osint(
                query_value=query_value,
                scan_type=scan_type,
                modules=modules,
                progress_callback=update_progress,
            )

            logger.info(f"Scan {scan_id}: {len(raw_findings)} raw findings from OSINT engine")

            # ── 5. Classify and persist findings ────────────────────────────
            for raw in raw_findings:
                classification = classifier.classify(raw)

                finding = Finding(
                    scan_id=scan.id,
                    user_id=scan.user_id,
                    finding_type=_coerce_finding_type(raw.get("finding_type", "search_engine")),
                    source_url=raw.get("source_url"),
                    source_domain=raw.get("source_domain"),
                    source_title=raw.get("source_title"),
                    source_name=raw.get("source_name"),
                    severity=classification.severity,
                    risk_score=classification.risk_score,
                    description=raw.get("description") or classification.reasoning,
                    exposed_data_types=raw.get("exposed_data_types", []),
                    identity_theft_risk=classification.risk_factors.get("identity_theft_risk", False),
                    financial_risk=classification.risk_factors.get("financial_risk", False),
                    reputation_risk=classification.risk_factors.get("reputation_risk", False),
                    credential_exposure=classification.risk_factors.get("credential_exposure", False),
                    government_id_exposure=classification.risk_factors.get("government_id_exposure", False),
                    raw_data=raw.get("raw_data"),
                    snippet=raw.get("snippet"),
                )
                db.add(finding)
                sev = classification.severity
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

            # ── 6. Calculate exposure score ──────────────────────────────────
            exposure_score = classifier.calculate_overall_exposure_score(raw_findings)

            # ── 7. Update scan record ────────────────────────────────────────
            scan.status = ScanStatus.COMPLETED
            scan.completed_at = datetime.now(timezone.utc)
            scan.progress = 100
            scan.total_findings = len(raw_findings)
            scan.critical_count = severity_counts.get("critical", 0)
            scan.high_count = severity_counts.get("high", 0)
            scan.medium_count = severity_counts.get("medium", 0)
            scan.low_count = severity_counts.get("low", 0)
            scan.exposure_score = exposure_score
            scan.modules_completed = modules

            await db.commit()

            # ── 8. Dispatch report generation task ──────────────────────────
            from app.tasks.report_tasks import generate_evidence_report_task
            generate_evidence_report_task.delay(scan_id)

            # ── 9. Notify user if significant findings ───────────────────────
            if severity_counts["critical"] > 0 or severity_counts["high"] > 0:
                await _notify_scan_complete(db, scan, severity_counts)

            logger.info(
                f"Scan {scan_id} COMPLETED | "
                f"critical={severity_counts['critical']} "
                f"high={severity_counts['high']} "
                f"medium={severity_counts['medium']} "
                f"low={severity_counts['low']} "
                f"score={exposure_score}"
            )

        except Exception as exc:
            logger.error(f"Scan {scan_id} FAILED: {exc}", exc_info=True)
            scan.status = ScanStatus.FAILED
            scan.error_message = str(exc)[:500]
            scan.progress = 0
            await db.commit()
            raise


def _coerce_finding_type(raw_type: str) -> str:
    """Map raw string to valid FindingType enum value."""
    valid = {
        "breach", "social_media", "search_engine",
        "document", "dark_web_indicator", "whois",
        "paste_site", "forum", "news",
    }
    return raw_type if raw_type in valid else "search_engine"


async def _notify_scan_complete(db, scan, severity_counts: Dict):
    """Create an in-app notification when critical/high findings are found."""
    from app.models.takedown import Notification

    critical = severity_counts.get("critical", 0)
    high = severity_counts.get("high", 0)

    notif = Notification(
        user_id=scan.user_id,
        title="New Exposures Found" if (critical or high) else "Scan Complete",
        message=(
            f"Scan completed: {critical} critical and {high} high-severity "
            "exposures detected. Immediate action recommended."
        ) if (critical or high) else "Your OSINT scan completed. Review your findings.",
        notification_type="new_exposure",
        severity="critical" if critical > 0 else "warning",
        resource_type="scan",
        resource_id=str(scan.id),
    )
    db.add(notif)
    await db.commit()

    # ── Telegram alert (if configured) ────────────────────────────────────────
    if (critical or high):
        try:
            from app.services.notification_service import send_breach_alert_telegram
            from app.core.config import settings
            from app.models.user import User
            from sqlalchemy import select

            # Get user's Telegram chat_id from their profile (if stored)
            # For now use the default configured chat_id
            default_chat = getattr(settings, "TELEGRAM_DEFAULT_CHAT_ID", "")
            if default_chat:
                await send_breach_alert_telegram(
                    chat_id=default_chat,
                    email=scan.query_value,
                    finding_count=scan.total_findings,
                    critical=critical,
                    high=high,
                    scan_id=str(scan.id),
                )
        except Exception:
            pass  # Telegram is optional — never block main flow


# ── Maintenance tasks ─────────────────────────────────────────────────────────

@shared_task(name="app.tasks.scan_tasks.cleanup_old_data")
def cleanup_old_data():
    """Weekly cleanup of audit logs older than 90 days."""
    run_sync(_cleanup_async())


async def _cleanup_async():
    from sqlalchemy import delete
    from app.core.database import AsyncSessionLocal
    from app.models.user import AuditLog
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
        await db.commit()
    logger.info("Old audit logs cleaned up (>90 days)")
