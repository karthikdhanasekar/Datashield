"""
DataShield OSINT - Authentication API Tests
Uses the shared conftest.py fixtures (PostgreSQL test DB).
"""
import pytest
from httpx import AsyncClient


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "DataShield OSINT"


@pytest.mark.asyncio
async def test_health_ready(client):
    resp = await client.get("/health/ready")
    assert resp.status_code in (200, 503)  # 503 if Redis not available in test
    data = resp.json()
    assert "status" in data
    assert "checks" in data


# ── Registration ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_user(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "newuser@datashield.com",
        "password": "Test@1234!",
        "full_name": "New User",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@datashield.com"
    assert data["role"] == "individual"
    assert data["status"] == "pending_verification"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "email": "dup@datashield.com",
        "password": "Test@1234!",
        "full_name": "Dup User",
    }
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_weak_password_rejected(client):
    """Passwords not meeting strength rules are rejected with 422."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "weakpwd@datashield.com",
        "password": "weak",
        "full_name": "Weak User",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_missing_email_rejected(client):
    resp = await client.post("/api/v1/auth/register", json={
        "password": "Test@1234!",
        "full_name": "No Email",
    })
    assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_unverified_user_is_rejected(client):
    """Unverified users must verify their email before receiving tokens."""
    await client.post("/api/v1/auth/register", json={
        "email": "unverified@datashield.com",
        "password": "Test@1234!",
        "full_name": "Unverified",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "unverified@datashield.com",
        "password": "Test@1234!",
    })
    assert resp.status_code == 403
    assert "verify your email" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "wrongpass@datashield.com",
        "password": "Test@1234!",
        "full_name": "Wrong",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "wrongpass@datashield.com",
        "password": "WrongPassword!",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nobody@datashield.com",
        "password": "Test@1234!",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_verified_user(client, registered_user):
    """Fully verified user receives valid tokens."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user_role"] == "individual"
    assert data["mfa_required"] is False


# ── Protected routes ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_requires_auth(client):
    """GET /me without token → 401 (FastAPI HTTPBearer)."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_token(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_scan_requires_auth(client):
    """Scan endpoint without token → 401."""
    resp = await client.post("/api/v1/scans/", json={
        "scan_type": "email",
        "query_value": "test@example.com",
    })
    assert resp.status_code == 401


# ── Password reset ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_password_reset_request_always_202(client):
    """Always returns 202 to prevent user enumeration."""
    resp = await client.post("/api/v1/auth/password-reset/request", json={
        "email": "nonexistent999@datashield.com",
    })
    assert resp.status_code == 202
    assert "message" in resp.json()


# ── Token refresh ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_refresh(client, registered_user):
    """Valid refresh token → new access token."""
    login = await client.post("/api/v1/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_invalid_refresh_token(client):
    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": "this.is.not.a.valid.jwt",
    })
    assert resp.status_code == 401
