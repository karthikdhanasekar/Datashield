"""
DataShield OSINT - Celery Application
Async task queue for OSINT scans, monitoring, and notifications
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "datashield",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.scan_tasks",
        "app.tasks.monitoring_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.takedown_tasks",
        "app.tasks.report_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.scan_tasks.*": {"queue": "scans"},
        "app.tasks.monitoring_tasks.*": {"queue": "monitoring"},
        "app.tasks.notification_tasks.*": {"queue": "notifications"},
        "app.tasks.takedown_tasks.*": {"queue": "takedowns"},
        "app.tasks.report_tasks.*": {"queue": "reports"},
    },
    # Periodic tasks (beat schedule)
    beat_schedule={
        # Run monitoring checks every hour
        "monitor-active-urls-hourly": {
            "task": "app.tasks.monitoring_tasks.run_monitoring_cycle",
            "schedule": crontab(minute=0),
        },
        # Daily full re-scan of all active monitors
        "daily-full-rescan": {
            "task": "app.tasks.monitoring_tasks.daily_full_rescan",
            "schedule": crontab(hour=2, minute=0),
        },
        # Clean up old audit logs weekly
        "cleanup-old-audit-logs": {
            "task": "app.tasks.scan_tasks.cleanup_old_data",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),
        },
        # Send pending takedown reminders daily
        "takedown-reminders": {
            "task": "app.tasks.takedown_tasks.send_pending_reminders",
            "schedule": crontab(hour=9, minute=0),
        },
    },
)
