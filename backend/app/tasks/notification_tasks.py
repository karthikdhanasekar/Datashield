"""
DataShield OSINT - Notification Delivery Celery Tasks
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


@shared_task(name="app.tasks.notification_tasks.send_user_notification")
def send_user_notification(notification_id: str):
    """Deliver a notification via email and/or SMS based on user preferences."""
    run_sync(_send_notification(notification_id))


async def _send_notification(notification_id: str):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.takedown import Notification
    from app.models.user import User
    from app.services.notification_service import send_email, send_sms

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notif = result.scalar_one_or_none()
        if not notif:
            return

        user_result = await db.execute(select(User).where(User.id == notif.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return

        if user.notification_email and user.email:
            success = await send_email(
                to_email=user.email,
                subject=f"[DataShield] {notif.title}",
                body=notif.message,
            )
            if success:
                notif.email_sent = True

        if user.notification_sms and user.phone_number:
            success = await send_sms(
                phone_number=user.phone_number,
                message=f"DataShield: {notif.title} — {notif.message[:100]}",
            )
            if success:
                notif.sms_sent = True

        await db.commit()


@shared_task(name="app.tasks.notification_tasks.send_bulk_alerts")
def send_bulk_alerts(user_ids: list, title: str, message: str, notif_type: str):
    """Send the same notification to multiple users."""
    run_sync(_send_bulk(user_ids, title, message, notif_type))


async def _send_bulk(user_ids: list, title: str, message: str, notif_type: str):
    from app.core.database import AsyncSessionLocal
    from app.models.takedown import Notification

    async with AsyncSessionLocal() as db:
        for uid in user_ids:
            notif = Notification(
                user_id=uid,
                title=title,
                message=message,
                notification_type=notif_type,
                severity="info",
            )
            db.add(notif)
        await db.commit()
    logger.info(f"Bulk notifications created for {len(user_ids)} users")
