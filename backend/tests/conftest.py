"""
DataShield OSINT — Pytest shared fixtures.

Design:
- NullPool: every DB call gets a fresh connection, no loop binding
- All fixtures are function-scoped (default pytest-asyncio 0.23 behavior)
- Tables are dropped/created once via a session-scoped sync call
- BackgroundTasks are disabled to prevent post-test async activity
"""
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient, ASGITransport
from slowapi import _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text, create_engine
from sqlalchemy.ext.asyncio import (
    create_async_engine, async_sessionmaker, AsyncSession
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db


# ── DB URLs ───────────────────────────────────────────────────────────────────
_db_base = settings.DATABASE_URL[: settings.DATABASE_URL.rfind("/")]
TEST_ASYNC_URL = f"{_db_base}/datashield_test"


# ── Create tables via pytest_configure hook (runs before any test collection) ─
def pytest_configure(config):
    """Create all test DB tables synchronously before tests start."""
    import os
    db_url = os.environ.get("DATABASE_URL", settings.DATABASE_URL)
    db_base = db_url[: db_url.rfind("/")]
    sync_url = (db_base + "/datashield_test").replace(
        "postgresql+asyncpg", "postgresql+psycopg2"
    )
    try:
        # Import all models so Base.metadata is fully populated
        import app.models.user   # noqa
        import app.models.scan   # noqa
        import app.models.takedown  # noqa
        sync_engine = create_engine(sync_url, echo=False)
        Base.metadata.drop_all(sync_engine)
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()
        print(f"\n[conftest] Test DB tables created: {sync_url}")
    except Exception as e:
        print(f"\n[conftest] WARNING: Could not create test tables: {e}")


# ── Async engine with NullPool (new connection per call, no loop binding) ──────
_async_engine = create_async_engine(TEST_ASYNC_URL, poolclass=NullPool, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def _override_get_db():
    async with TestSessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


# ── Test app (no GZipMiddleware) ──────────────────────────────────────────────
def _make_app() -> FastAPI:
    from app.api.v1.auth import router as auth_r
    from app.api.v1.scans import router as scan_r
    from app.api.v1.reports import router as rep_r
    from app.api.v1.ai import router as ai_r
    from app.api.v1.admin import router as admin_r
    from app.api.v1.takedowns import (
        takedown_router, monitor_router,
        complaint_router, notification_router,
    )
    from prometheus_fastapi_instrumentator import Instrumentator

    app = FastAPI(title="Test", docs_url=None, redoc_url=None)

    # Use memory-based limiter in tests — avoids Redis async teardown issue
    from limits.storage import MemoryStorage
    from slowapi import Limiter
    lim = Limiter(key_func=get_remote_address, storage_uri="memory://")
    app.state.limiter = lim
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )
    Instrumentator().instrument(app)

    P = "/api/v1"
    app.include_router(auth_r,              prefix=P)
    app.include_router(scan_r,              prefix=P)
    app.include_router(rep_r,               prefix=P)
    app.include_router(ai_r,                prefix=P)
    app.include_router(admin_r,             prefix=P)
    app.include_router(takedown_router,     prefix=P)
    app.include_router(monitor_router,      prefix=P)
    app.include_router(complaint_router,    prefix=P)
    app.include_router(notification_router, prefix=P)

    @app.get("/health")
    async def _h():
        return {"status": "healthy", "service": "DataShield OSINT",
                "version": settings.APP_VERSION}

    @app.get("/health/ready")
    async def _r():
        return {"status": "ready", "checks": {"redis": "ok"}}

    return app


_app = _make_app()
_app.dependency_overrides[get_db] = _override_get_db


# ── Patch Redis to use a simple in-memory dict in tests ──────────────────────
@pytest.fixture(autouse=True)
def _patch_redis(monkeypatch):
    """
    Replace every Redis async call with in-memory no-ops so no real Redis
    connections are opened (and no event-loop-closed errors on teardown).

    Also resets the _redis_client singleton before each test so it cannot
    carry a stale connection from a previous test's loop.
    """
    import app.core.redis_client as rc

    # Reset the singleton so a new test can't pick up a dead connection
    monkeypatch.setattr(rc, "_redis_client", None)

    async def _noop_set(*a, **kw):    return None
    async def _noop_get(*a, **kw):    return None
    async def _noop_del(*a, **kw):    return None
    async def _noop_del_p(*a, **kw):  return 0
    async def _false(*a, **kw):       return False
    async def _noop_bl(*a, **kw):     return None

    monkeypatch.setattr(rc, "cache_set",            _noop_set)
    monkeypatch.setattr(rc, "cache_get",            _noop_get)
    monkeypatch.setattr(rc, "cache_delete",         _noop_del)
    monkeypatch.setattr(rc, "cache_delete_pattern", _noop_del_p)
    monkeypatch.setattr(rc, "add_to_blacklist",     _noop_bl)
    monkeypatch.setattr(rc, "is_blacklisted",       _false)

    # Also patch get_redis itself so any code that calls it directly
    # (e.g. redis_client.py:70 inside deps.py) returns a mock object
    # instead of opening a real TCP connection.
    class _FakeRedis:
        async def exists(self, *a):  return 0
        async def setex(self, *a):   return True
        async def get(self, *a):     return None
        async def delete(self, *a):  return 0
        async def keys(self, *a):    return []
        async def ping(self):        return True
        async def aclose(self):      return None

    async def _fake_get_redis():
        return _FakeRedis()

    monkeypatch.setattr(rc, "get_redis", _fake_get_redis)


# ── Patch BackgroundTasks globally to avoid post-test async activity ──────────
@pytest.fixture(autouse=True)
def _no_background_tasks(monkeypatch):
    """Silence all BackgroundTasks — prevents loop-closed errors on teardown."""
    from starlette.background import BackgroundTasks
    monkeypatch.setattr(BackgroundTasks, "add_task", lambda *a, **kw: None)


# ── Clean DB rows before every test ──────────────────────────────────────────
_TABLES = [
    "audit_logs", "user_sessions", "takedown_status_history",
    "takedown_requests", "monitor_check_history", "monitor_configs",
    "evidence_reports", "findings", "scan_requests",
    "cybercrime_complaints", "notifications", "organizations", "users",
]


@pytest.fixture(autouse=True)
async def _clean_db():
    async with TestSessionLocal() as s:
        for t in _TABLES:
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()
    yield
    # Also clean after so next test starts fresh
    async with TestSessionLocal() as s:
        for t in _TABLES:
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=_app),
        base_url="http://test",
        timeout=10.0,
    ) as ac:
        yield ac


@pytest.fixture
async def registered_user(client):
    payload = {
        "email": "user@datashield.com",
        "password": "User@1234!",
        "full_name": "Test User",
    }
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201, f"Register failed: {r.text}"

    from app.models.user import User, UserStatus
    from sqlalchemy import update
    async with TestSessionLocal() as db:
        await db.execute(
            update(User).where(User.email == payload["email"])
            .values(email_verified=True, status=UserStatus.ACTIVE)
        )
        await db.commit()
    return payload


@pytest.fixture
async def auth_headers(client, registered_user):
    r = await client.post("/api/v1/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client):
    payload = {
        "email": "admin@datashield.com",
        "password": "Admin@1234!",
        "full_name": "Admin",
    }
    await client.post("/api/v1/auth/register", json=payload)

    from app.models.user import User, UserStatus, UserRole
    from sqlalchemy import update
    async with TestSessionLocal() as db:
        await db.execute(
            update(User).where(User.email == payload["email"])
            .values(email_verified=True, status=UserStatus.ACTIVE, role=UserRole.ADMIN)
        )
        await db.commit()

    r = await client.post("/api/v1/auth/login", json={
        "email": payload["email"],
        "password": payload["password"],
    })
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
