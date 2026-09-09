"""
DataShield OSINT - Structured Logging Configuration
Uses structlog for JSON-formatted, contextual log output
"""
import logging
import sys
import structlog
from app.core.config import settings


def configure_logging() -> None:
    """Configure structlog with JSON output for production, pretty for dev."""

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.ENVIRONMENT == "development" or settings.DEBUG:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=False)
        ]
    else:
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.DEBUG else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
    )

    for lib in ["httpx", "httpcore", "urllib3", "botocore", "boto3"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
