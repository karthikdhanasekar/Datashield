"""
DataShield OSINT - Monitoring Celery Tasks
Periodic re-checking of exposed URLs for removal status
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def run_sync(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(name="app.tasks.monitoring_tasks.run_monitoring_cycle")
def run_monitoring_cycle():
    """Check all due monitors for URL exposure status."""
    run_sync(_run_monitoring_cycle())


async def _run_monitoring_cycle():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.takedown import MonitorConfig, MonitorInterval

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MonitorConfig).where(
                MonitorConfig.is_active == True,  # noqa: E712
                (MonitorConfig.next_check_at == None) | (MonitorConfig.next_check_at <= now),
            )
        )
        monitors = result.scalars().all()
        logger.info(f"Running monitoring cycle for {len(monitors)} monitors")

        for monitor in monitors:
            check_single_monitor.delay(str(monitor.id))


@shared_task(
    name="app.tasks.monitoring_tasks.check_single_monitor",
    soft_time_limit=60,
    time_limit=90,
)
def check_single_monitor(monitor_id: str):
    """Check a single monitor URL for exposure status."""
    run_sync(_check_single_monitor(monitor_id))


async def _check_single_monitor(monitor_id: str):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.takedown import MonitorConfig, MonitorCheckHistory, MonitorInterval, Notification
    import httpx

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MonitorConfig).where(MonitorConfig.id == monitor_id)
        )
        monitor = result.scalar_one_or_none()
        if not monitor:
            return

        # Check if URL is still accessible
        status = "unknown"
        http_code = None
        accessible = False
        error_msg = None

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.head(monitor.target_url)
                http_code = resp.status_code
                accessible = resp.status_code < 400
                status = "exposed" if accessible else "removed"
        except Exception as e:
            status = "error"
            error_msg = str(e)[:200]
            monitor.consecutive_failures += 1

        if status != "error":
            monitor.consecutive_failures = 0

        # Determine next check time
        interval_map = {
            MonitorInterval.DAILY: timedelta(days=1),
            MonitorInterval.WEEKLY: timedelta(weeks=1),
            MonitorInterval.MONTHLY: timedelta(days=30),
        }
        monitor.next_check_at = now + interval_map.get(monitor.monitor_interval, timedelta(weeks=1))
        monitor.last_checked_at = now
        monitor.last_status = status

        # Record history
        history = MonitorCheckHistory(
            monitor_id=monitor.id,
            status=status,
            http_status_code=http_code,
            page_accessible=accessible,
            data_still_present=accessible,
            error_message=error_msg,
        )
        db.add(history)

        # Alert if data reappeared or new exposure
        prev_status = monitor.last_status
        if (
            monitor.alert_on_reappear
            and prev_status == "removed"
            and status == "exposed"
        ):
            notif = Notification(
                user_id=monitor.user_id,
                title="Data Reappeared",
                message=f"Previously removed data has reappeared at {monitor.target_domain}.",
                notification_type="monitor_alert",
                severity="critical",
                resource_type="monitor",
                resource_id=str(monitor.id),
            )
            db.add(notif)

        await db.commit()
        logger.info(f"Monitor {monitor_id}: {status} (HTTP {http_code})")


@shared_task(name="app.tasks.monitoring_tasks.daily_full_rescan")
def daily_full_rescan():
    """Daily: trigger re-scan for all active monitors marked as daily."""
    run_sync(_daily_full_rescan())


async def _daily_full_rescan():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.takedown import MonitorConfig, MonitorInterval

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MonitorConfig).where(
                MonitorConfig.is_active == True,  # noqa: E712
                MonitorConfig.monitor_interval == MonitorInterval.DAILY.value,
            )
        )
        for monitor in result.scalars().all():
            check_single_monitor.delay(str(monitor.id))
    logger.info("Daily full rescan dispatched")
