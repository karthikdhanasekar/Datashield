"""
DataShield OSINT - Takedown Celery Tasks
Email delivery and follow-up for removal requests
"""
import asyncio
from datetime import datetime, timezone, timedelta
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
    name="app.tasks.takedown_tasks.send_takedown_request_task",
    max_retries=3,
    default_retry_delay=60,
)
def send_takedown_request_task(takedown_id: str):
    """Send a takedown email to the website owner/abuse contact."""
    run_sync(_send_takedown(takedown_id))


async def _send_takedown(takedown_id: str):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.takedown import TakedownRequest, TakedownStatus, TakedownStatusHistory, Notification
    from app.services.notification_service import send_email

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TakedownRequest).where(TakedownRequest.id == takedown_id)
        )
        takedown = result.scalar_one_or_none()
        if not takedown:
            return

        target_email = (
            takedown.contact_email
            or takedown.abuse_email
            or takedown.privacy_officer_email
        )

        if not target_email:
            logger.warning(f"Takedown {takedown_id}: no contact email found, skipping send")
            takedown.status = TakedownStatus.PENDING
            await db.commit()
            return

        try:
            await send_email(
                to_email=target_email,
                subject=takedown.subject,
                body=takedown.body,
                reply_to=None,
            )
            takedown.status = TakedownStatus.SENT
            takedown.sent_at = datetime.now(timezone.utc)
            takedown.next_follow_up_at = datetime.now(timezone.utc) + timedelta(days=14)

            history = TakedownStatusHistory(
                takedown_id=takedown.id,
                old_status=TakedownStatus.PENDING,
                new_status=TakedownStatus.SENT,
                note=f"Sent to {target_email}",
                changed_by="system",
            )
            db.add(history)

            # Notify user
            notif = Notification(
                user_id=takedown.user_id,
                title="Takedown Request Sent",
                message=f"Your removal request for {takedown.target_domain} has been sent to {target_email}.",
                notification_type="takedown_sent",
                severity="info",
                resource_type="takedown",
                resource_id=str(takedown.id),
            )
            db.add(notif)

        except Exception as e:
            logger.error(f"Failed to send takedown {takedown_id}: {e}")
            takedown.status = TakedownStatus.FAILED

        await db.commit()


@shared_task(name="app.tasks.takedown_tasks.send_pending_reminders")
def send_pending_reminders():
    """Send follow-up reminders for unanswered takedown requests."""
    run_sync(_send_pending_reminders())


async def _send_pending_reminders():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.takedown import TakedownRequest, TakedownStatus, TakedownStatusHistory, Notification
    from app.services.notification_service import send_email

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TakedownRequest).where(
                TakedownRequest.status.in_([TakedownStatus.SENT, TakedownStatus.ACKNOWLEDGED]),
                TakedownRequest.next_follow_up_at != None,
                TakedownRequest.next_follow_up_at <= now,
            )
        )
        takedowns = result.scalars().all()
        logger.info(f"Sending {len(takedowns)} follow-up reminders")

        for t in takedowns:
            # Escalate after 3 follow-ups
            if t.follow_up_count >= 3:
                t.status = TakedownStatus.ESCALATED
                t.escalated_at = now
                t.escalation_reason = "No response after 3 follow-up attempts"

                notif = Notification(
                    user_id=t.user_id,
                    title="Takedown Escalated",
                    message=(
                        f"Removal request for {t.target_domain} has been escalated "
                        "after no response. Consider filing a formal complaint."
                    ),
                    notification_type="escalation_required",
                    severity="warning",
                    resource_type="takedown",
                    resource_id=str(t.id),
                )
                db.add(notif)
                history = TakedownStatusHistory(
                    takedown_id=t.id,
                    old_status=t.status,
                    new_status=TakedownStatus.ESCALATED,
                    note="Auto-escalated after 3 follow-ups",
                    changed_by="system",
                )
                db.add(history)
            else:
                # Send follow-up
                target_email = t.contact_email or t.abuse_email
                if target_email:
                    try:
                        await send_email(
                            to_email=target_email,
                            subject=f"Follow-up: {t.subject}",
                            body=f"This is a follow-up to our previous removal request.\n\n{t.body}",
                        )
                        t.follow_up_count += 1
                        t.next_follow_up_at = now + timedelta(days=14)
                    except Exception as e:
                        logger.error(f"Follow-up send failed: {e}")

        await db.commit()
