"""
DataShield OSINT - Report Generation Celery Tasks
"""
import asyncio
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def run_sync(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    name="app.tasks.report_tasks.generate_evidence_report",
    soft_time_limit=120,
    time_limit=150,
)
def generate_evidence_report_task(scan_id: str):
    """Generate and store evidence report for a completed scan."""
    run_sync(_generate_report(scan_id))


async def _generate_report(scan_id: str):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.scan import ScanRequest, Finding, EvidenceReport
    from app.models.user import User
    from app.services.report_service import generate_evidence_report

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ScanRequest).where(ScanRequest.id == scan_id))
        scan = result.scalar_one_or_none()
        if not scan:
            return

        user_result = await db.execute(select(User).where(User.id == scan.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return

        findings_result = await db.execute(
            select(Finding).where(Finding.scan_id == scan_id)
        )
        findings = findings_result.scalars().all()

        try:
            report_data = await generate_evidence_report(scan, findings, user)

            report = EvidenceReport(
                scan_id=scan.id,
                user_id=scan.user_id,
                report_title=f"Evidence Report — {scan.scan_type.value} Scan",
                finding_count=len(findings),
                pdf_url=report_data.get("pdf_url"),
                json_url=report_data.get("json_url"),
                csv_url=report_data.get("csv_url"),
                report_hash=report_data.get("report_hash"),
            )
            db.add(report)
            await db.commit()
            logger.info(f"Report generated for scan {scan_id}")

        except Exception as e:
            logger.error(f"Report generation failed for {scan_id}: {e}")
