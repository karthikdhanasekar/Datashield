"""
DataShield OSINT — FastAPI Application Entry Point
Production-ready privacy protection platform backend
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import structlog

from app.core.config import settings
from app.core.database import init_db
from app.core.redis_client import close_redis
from app.core.logging import configure_logging
from app.api.v1.auth import router as auth_router
from app.api.v1.scans import router as scans_router
from app.api.v1.ai import router as ai_router
from app.api.v1.admin import router as admin_router
from app.api.v1.reports import router as reports_router
from app.api.v1.takedowns import (
    takedown_router, monitor_router, complaint_router, notification_router
)

logger = structlog.get_logger(__name__)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    configure_logging()
    logger.info("DataShield OSINT starting up", version=settings.APP_VERSION)
    await init_db()
    logger.info("Database initialized")
    # Initialize Elasticsearch indices
    try:
        from app.services.elasticsearch_service import ensure_indices
        await ensure_indices()
        logger.info("Elasticsearch indices ready")
    except Exception as e:
        logger.warning("Elasticsearch not available at startup", error=str(e))
    yield
    await close_redis()
    logger.info("DataShield OSINT shutting down")


# ── App Factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="DataShield OSINT API",
    description=(
        "Privacy protection platform API — discover, monitor, and remove "
        "exposed personal information from the public internet."
    ),
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Exception Handlers ────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " → ".join(str(l) for l in error["loc"])
        errors.append({"field": field, "message": error["msg"]})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


# ── Prometheus Monitoring ────────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# ── Router Registration ──────────────────────────────────────────────────────
API_V1 = "/api/v1"

app.include_router(auth_router, prefix=API_V1)
app.include_router(scans_router, prefix=API_V1)
app.include_router(reports_router, prefix=API_V1)
app.include_router(ai_router, prefix=API_V1)
app.include_router(admin_router, prefix=API_V1)
app.include_router(takedown_router, prefix=API_V1)
app.include_router(monitor_router, prefix=API_V1)
app.include_router(complaint_router, prefix=API_V1)
app.include_router(notification_router, prefix=API_V1)


# ── Health Checks ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "DataShield OSINT", "version": settings.APP_VERSION}


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Check that all dependencies are ready."""
    checks = {}
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )


# ── WebSocket — Real-time scan progress ───────────────────────────────────────

@app.websocket("/ws/scan/{scan_id}")
async def scan_progress_ws(websocket: WebSocket, scan_id: str):
    """
    WebSocket endpoint for real-time scan progress.

    The client connects with a valid JWT in the Authorization header or
    as a query param ?token=<jwt>.

    Messages sent (JSON):
      { "type": "progress", "data": { scan fields... } }
      { "type": "finding",  "data": { finding fields... } }
      { "type": "complete", "data": { scan fields... } }
      { "type": "error",    "data": { "message": "..." } }

    The connection is closed automatically when the scan completes or fails.
    """
    import asyncio
    import json
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.core.security import decode_token
    from app.models.scan import ScanRequest, ScanStatus, Finding
    from jose import JWTError

    # ── Auth via query param (WebSocket can't send headers easily) ────────────
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001)
            return
    except JWTError:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    logger.info("WebSocket connected", scan_id=scan_id, user_id=user_id)

    last_finding_count = 0
    last_progress = -1

    try:
        while True:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ScanRequest).where(
                        ScanRequest.id == scan_id,
                        ScanRequest.user_id == user_id,
                    )
                )
                scan = result.scalar_one_or_none()

                if not scan:
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": "Scan not found or access denied"},
                    })
                    break

                # Send progress update if changed
                if scan.progress != last_progress:
                    last_progress = scan.progress
                    await websocket.send_json({
                        "type": "progress",
                        "data": {
                            "id":               str(scan.id),
                            "status":           scan.status.value,
                            "progress":         scan.progress,
                            "total_findings":   scan.total_findings,
                            "critical_count":   scan.critical_count,
                            "high_count":       scan.high_count,
                            "medium_count":     scan.medium_count,
                            "low_count":        scan.low_count,
                            "exposure_score":   scan.exposure_score,
                            "modules_run":      scan.modules_run or [],
                            "modules_completed":scan.modules_completed or [],
                        },
                    })

                # Push new findings since last check
                if scan.total_findings > last_finding_count:
                    findings_result = await db.execute(
                        select(Finding)
                        .where(Finding.scan_id == scan_id)
                        .order_by(Finding.discovered_at.desc())
                        .limit(scan.total_findings - last_finding_count)
                    )
                    new_findings = findings_result.scalars().all()
                    last_finding_count = scan.total_findings

                    for f in reversed(new_findings):
                        await websocket.send_json({
                            "type": "finding",
                            "data": {
                                "id":             str(f.id),
                                "finding_type":   f.finding_type.value,
                                "source_name":    f.source_name,
                                "source_domain":  f.source_domain,
                                "source_title":   f.source_title,
                                "severity":       f.severity.value,
                                "risk_score":     f.risk_score,
                                "description":    f.description,
                                "snippet":        f.snippet,
                            },
                        })

                # Terminal states — send completion then close
                if scan.status in (ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED):
                    await websocket.send_json({
                        "type": "complete" if scan.status == ScanStatus.COMPLETED else "error",
                        "data": {
                            "status":         scan.status.value,
                            "total_findings": scan.total_findings,
                            "exposure_score": scan.exposure_score,
                            "error_message":  scan.error_message,
                        },
                    })
                    break

            await asyncio.sleep(1.5)   # poll DB every 1.5s and push diffs

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", scan_id=scan_id)
    except Exception as e:
        logger.error("WebSocket error", scan_id=scan_id, error=str(e))
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
