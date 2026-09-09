"""
DataShield OSINT - Scan API Tests
Uses shared conftest.py fixtures (PostgreSQL test DB).
"""
import pytest
from unittest.mock import patch, MagicMock


# ── Auth guard ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_scan_requires_auth(client):
    """No token → 401."""
    resp = await client.post("/api/v1/scans/", json={
        "scan_type": "email",
        "query_value": "test@example.com",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_scans_requires_auth(client):
    resp = await client.get("/api/v1/scans/")
    assert resp.status_code == 401


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_scan_invalid_type(client, auth_headers):
    resp = await client.post("/api/v1/scans/", json={
        "scan_type": "not_a_real_type",
        "query_value": "test@example.com",
    }, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_scan_empty_query(client, auth_headers):
    resp = await client.post("/api/v1/scans/", json={
        "scan_type": "email",
        "query_value": "",
    }, headers=auth_headers)
    assert resp.status_code == 422


# ── Scan creation ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.tasks.scan_tasks.run_osint_scan.delay")
async def test_create_email_scan_succeeds(mock_delay, client, auth_headers):
    """Scan creation returns 202 and dispatches Celery task."""
    mock_delay.return_value = MagicMock(id="mock-celery-task-id")
    resp = await client.post("/api/v1/scans/", json={
        "scan_type": "email",
        "query_value": "test@example.com",
        "modules": ["breach", "search_engine"],
    }, headers=auth_headers)
    assert resp.status_code == 202
    data = resp.json()
    assert data["scan_type"] == "email"
    assert data["status"] == "pending"
    assert data["progress"] == 0


@pytest.mark.asyncio
@patch("app.tasks.scan_tasks.run_osint_scan.delay")
async def test_create_username_scan(mock_delay, client, auth_headers):
    mock_delay.return_value = MagicMock(id="mock-task-2")
    resp = await client.post("/api/v1/scans/", json={
        "scan_type": "username",
        "query_value": "johndoe",
        "modules": ["maigret", "social_media"],
    }, headers=auth_headers)
    assert resp.status_code == 202
    assert resp.json()["scan_type"] == "username"


# ── Scan listing ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_scans_empty(client, auth_headers):
    resp = await client.get("/api/v1/scans/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_scan_list_pagination(client, auth_headers):
    resp = await client.get("/api/v1/scans/?page=1&page_size=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 5


@pytest.mark.asyncio
async def test_get_scan_not_found(client, auth_headers):
    resp = await client.get(
        "/api/v1/scans/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Exposure score ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exposure_score_endpoint(client, auth_headers):
    resp = await client.get(
        "/api/v1/scans/dashboard/exposure-score",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "risk_level" in data
    assert "breakdown" in data
    assert "recommendations" in data
    assert 0 <= data["score"] <= 100
    assert data["risk_level"] in ("safe", "low", "medium", "high", "critical")
    assert isinstance(data["recommendations"], list)


# ── Finding update ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_finding_not_found(client, auth_headers):
    resp = await client.patch(
        "/api/v1/scans/findings/00000000-0000-0000-0000-000000000000",
        json={"is_false_positive": True},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Isolation: other user can't access my scan ───────────────────────────────

@pytest.mark.asyncio
@patch("app.tasks.scan_tasks.run_osint_scan.delay")
async def test_scan_user_isolation(mock_delay, client, auth_headers):
    """A user cannot access another user's scan."""
    mock_delay.return_value = MagicMock(id="mock-task-iso")

    # Create a scan as the fixture user
    create = await client.post("/api/v1/scans/", json={
        "scan_type": "phone",
        "query_value": "+919876543210",
    }, headers=auth_headers)
    assert create.status_code == 202
    scan_id = create.json()["id"]

    # Register a second user
    await client.post("/api/v1/auth/register", json={
        "email": "otheruser@datashield.com",
        "password": "Other@1234!",
        "full_name": "Other User",
    })
    from app.models.user import User, UserStatus
    from sqlalchemy import update
    from tests.conftest import TestSessionLocal
    async with TestSessionLocal() as db:
        await db.execute(
            update(User)
            .where(User.email == "otheruser@datashield.com")
            .values(email_verified=True, status=UserStatus.ACTIVE)
        )
        await db.commit()

    other_login = await client.post("/api/v1/auth/login", json={
        "email": "otheruser@datashield.com",
        "password": "Other@1234!",
    })
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    # Other user should get 404 on first user's scan
    resp = await client.get(f"/api/v1/scans/{scan_id}", headers=other_headers)
    assert resp.status_code == 404
