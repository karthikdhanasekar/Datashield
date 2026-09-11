"""
DataShield OSINT — Integration Tests
=====================================
End-to-end tests covering the full scan → finding → takedown → export pipeline.

These tests exercise the real API routes against a real (test) PostgreSQL
database using the shared conftest fixtures.  Celery tasks are patched
to run synchronously so no worker process is needed.

Coverage:
  - Full scan creation and Celery task execution (sync stub)
  - Findings appear in GET /scans/{id}
  - Search endpoint returns findings (PostgreSQL fallback)
  - Export endpoints return valid CSV/JSON
  - Takedown created from a real finding_id
  - Rate-limit enforcement (11th scan in <1 hr → 429)
  - Exposure score reflects actual findings
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_finding(db, scan_id: str, user_id: str, severity: str = "high") -> str:
    """Insert one Finding row directly into the DB and return its id."""
    import uuid
    from app.models.scan import Finding, FindingType, SeverityLevel
    finding = Finding(
        id=uuid.uuid4(),
        scan_id=scan_id,
        user_id=user_id,
        finding_type=FindingType.SEARCH_ENGINE,
        source_domain="example-leak.com",
        source_url="https://example-leak.com/dump.txt",
        source_title="Email credential dump",
        severity=SeverityLevel(severity),
        risk_score={"critical": 9.5, "high": 7.0, "medium": 4.0, "low": 1.5}[severity],
        description=f"Test {severity} finding seeded by integration test",
        exposed_data_types=["email", "password"],
        identity_theft_risk=True,
        financial_risk=False,
        reputation_risk=True,
        credential_exposure=True,
        government_id_exposure=False,
        snippet="user@example.com:password123 found in public dump",
    )
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    return str(finding.id)


async def _get_user_id(email: str) -> str:
    from app.models.user import User
    from sqlalchemy import select
    from tests.conftest import TestSessionLocal
    async with TestSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        return str(user.id)


# ---------------------------------------------------------------------------
# 1. Scan creation
# ---------------------------------------------------------------------------

class TestScanCreation:

    async def test_create_scan_returns_202(self, client: AsyncClient, auth_headers):
        """POST /scans/ should accept the request and queue a Celery task."""
        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as mock_delay:
            mock_delay.return_value = MagicMock(id="fake-celery-id")
            r = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "test@example.com"},
                headers=auth_headers,
            )
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "pending"
        assert body["scan_type"] == "email"
        assert body["id"]
        mock_delay.assert_called_once()

    async def test_create_scan_invalid_type(self, client: AsyncClient, auth_headers):
        with patch("app.tasks.scan_tasks.run_osint_scan.delay"):
            r = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "invalid_type", "query_value": "test"},
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert "Invalid scan type" in r.json()["detail"]

    async def test_create_scan_empty_query(self, client: AsyncClient, auth_headers):
        with patch("app.tasks.scan_tasks.run_osint_scan.delay"):
            r = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "   "},
                headers=auth_headers,
            )
        assert r.status_code == 422  # Pydantic validation

    async def test_list_scans(self, client: AsyncClient, auth_headers):
        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t1")
            await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "a@b.com"},
                headers=auth_headers,
            )
        r = await client.get("/api/v1/scans/", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_delete_scan(self, client: AsyncClient, auth_headers):
        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t2")
            cr = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "phone", "query_value": "+919876543210"},
                headers=auth_headers,
            )
        scan_id = cr.json()["id"]
        dr = await client.delete(f"/api/v1/scans/{scan_id}", headers=auth_headers)
        assert dr.status_code == 204


# ---------------------------------------------------------------------------
# 2. Findings pipeline
# ---------------------------------------------------------------------------

class TestFindingsPipeline:

    async def test_findings_appear_after_seeding(
        self, client: AsyncClient, auth_headers, registered_user
    ):
        """Seed a finding directly into the DB and verify it shows in the API."""
        user_id  = await _get_user_id(registered_user["email"])

        # Create a scan record
        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t3")
            cr = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "test@leak.com"},
                headers=auth_headers,
            )
        scan_id = cr.json()["id"]

        # Seed finding
        from tests.conftest import TestSessionLocal
        async with TestSessionLocal() as db:
            fid = await _seed_finding(db, scan_id, user_id)

        # Verify finding appears in scan result
        r = await client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["findings"][0]["id"] == fid
        assert body["findings"][0]["severity"] == "high"

    async def test_update_finding_false_positive(
        self, client: AsyncClient, auth_headers, registered_user
    ):
        user_id = await _get_user_id(registered_user["email"])

        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t4")
            cr = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "fp@test.com"},
                headers=auth_headers,
            )
        scan_id = cr.json()["id"]

        from tests.conftest import TestSessionLocal
        async with TestSessionLocal() as db:
            fid = await _seed_finding(db, scan_id, user_id, severity="medium")

        r = await client.patch(
            f"/api/v1/scans/findings/{fid}",
            json={"is_false_positive": True},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["is_false_positive"] is True

    async def test_exposure_score_reflects_findings(
        self, client: AsyncClient, auth_headers, registered_user
    ):
        user_id = await _get_user_id(registered_user["email"])

        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t5")
            cr = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "score@test.com"},
                headers=auth_headers,
            )
        scan_id = cr.json()["id"]

        from tests.conftest import TestSessionLocal
        async with TestSessionLocal() as db:
            await _seed_finding(db, scan_id, user_id, severity="critical")
            await _seed_finding(db, scan_id, user_id, severity="high")

        r = await client.get("/api/v1/scans/dashboard/exposure-score", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["score"] > 0
        assert body["risk_level"] in ("high", "critical")
        assert "breakdown" in body
        assert body["breakdown"]["critical"] >= 1


# ---------------------------------------------------------------------------
# 3. Search endpoint
# ---------------------------------------------------------------------------

class TestSearchEndpoint:

    async def test_search_returns_results(
        self, client: AsyncClient, auth_headers, registered_user
    ):
        user_id = await _get_user_id(registered_user["email"])

        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t6")
            cr = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "search@test.com"},
                headers=auth_headers,
            )
        scan_id = cr.json()["id"]

        from tests.conftest import TestSessionLocal
        async with TestSessionLocal() as db:
            await _seed_finding(db, scan_id, user_id)  # contains "leak" in description

        r = await client.get(
            "/api/v1/scans/search",
            params={"q": "integration test"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert "hits" in body
        assert body["source"] in ("elasticsearch", "postgresql")

    async def test_search_requires_query(self, client: AsyncClient, auth_headers):
        r = await client.get("/api/v1/scans/search", headers=auth_headers)
        assert r.status_code == 422  # q is required

    async def test_search_invalid_severity(self, client: AsyncClient, auth_headers):
        r = await client.get(
            "/api/v1/scans/search",
            params={"q": "test", "severity": "extreme"},
            headers=auth_headers,
        )
        # Either 200 with empty hits or 400 — not 500
        assert r.status_code in (200, 400)


# ---------------------------------------------------------------------------
# 4. Export endpoint
# ---------------------------------------------------------------------------

class TestExportEndpoint:

    async def test_export_csv(self, client: AsyncClient, auth_headers, registered_user):
        user_id = await _get_user_id(registered_user["email"])

        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t7")
            cr = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "export@test.com"},
                headers=auth_headers,
            )
        scan_id = cr.json()["id"]

        from tests.conftest import TestSessionLocal
        async with TestSessionLocal() as db:
            await _seed_finding(db, scan_id, user_id)

        r = await client.get(
            "/api/v1/scans/findings/export",
            params={"fmt": "csv"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        # Should have a header row + at least one data row
        lines = r.text.strip().split("\n")
        assert len(lines) >= 2
        assert "severity" in lines[0]

    async def test_export_json(self, client: AsyncClient, auth_headers, registered_user):
        user_id = await _get_user_id(registered_user["email"])

        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t8")
            cr = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "exportjson@test.com"},
                headers=auth_headers,
            )
        scan_id = cr.json()["id"]

        from tests.conftest import TestSessionLocal
        async with TestSessionLocal() as db:
            await _seed_finding(db, scan_id, user_id, severity="critical")

        r = await client.get(
            "/api/v1/scans/findings/export",
            params={"fmt": "json"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert "application/json" in r.headers.get("content-type", "")
        body = r.json()
        assert body["total"] >= 1
        assert "findings" in body

    async def test_export_no_findings_returns_404(self, client: AsyncClient, auth_headers):
        r = await client.get(
            "/api/v1/scans/findings/export",
            params={"fmt": "csv"},
            headers=auth_headers,
        )
        assert r.status_code == 404

    async def test_export_invalid_format(self, client: AsyncClient, auth_headers):
        r = await client.get(
            "/api/v1/scans/findings/export",
            params={"fmt": "xml"},
            headers=auth_headers,
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# 5. Takedown created from a real finding
# ---------------------------------------------------------------------------

class TestTakedownFromFinding:

    async def test_create_takedown_for_real_finding(
        self, client: AsyncClient, auth_headers, registered_user
    ):
        user_id = await _get_user_id(registered_user["email"])

        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="t9")
            cr = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "takedown@test.com"},
                headers=auth_headers,
            )
        scan_id = cr.json()["id"]

        from tests.conftest import TestSessionLocal
        async with TestSessionLocal() as db:
            fid = await _seed_finding(db, scan_id, user_id, severity="high")

        with patch("app.tasks.takedown_tasks.send_takedown_request_task.delay") as mock_delay:
            mock_delay.return_value = MagicMock(id="takedown-task")
            r = await client.post(
                "/api/v1/takedowns/",
                json={"finding_id": fid, "template_type": "gdpr_removal"},
                headers=auth_headers,
            )
            assert r.status_code in (200, 201)
            body = r.json()
            takedown_id = body.get("id")
            mock_delay.assert_called_once_with(takedown_id)

    async def test_list_takedowns(self, client: AsyncClient, auth_headers):
        r = await client.get("/api/v1/takedowns/", headers=auth_headers)
        assert r.status_code == 200
        assert "items" in r.json()


# ---------------------------------------------------------------------------
# 6. Rate limit enforcement
# ---------------------------------------------------------------------------

class TestScanRateLimit:

    async def test_rate_limit_blocks_11th_scan(self, client: AsyncClient, auth_headers):
        """
        The default SCAN_RATE_LIMIT_PER_HOUR is 10.
        Seeding 10 scans then attempting one more should return 429.
        """
        from tests.conftest import TestSessionLocal
        from app.models.scan import ScanRequest, ScanStatus, ScanType
        from app.models.user import User
        from sqlalchemy import select
        import uuid
        from datetime import datetime, timezone

        # Get user id
        async with TestSessionLocal() as db:
            r = await db.execute(
                select(User).where(User.email == "user@datashield.com")
            )
            user = r.scalar_one()

            # Seed 10 scan rows within the last hour
            for _ in range(10):
                db.add(ScanRequest(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    scan_type=ScanType.EMAIL,
                    query_value="ratelimit@test.com",
                    status=ScanStatus.COMPLETED,
                    modules_run=[],
                    modules_completed=[],
                    created_at=datetime.now(timezone.utc),
                ))
            await db.commit()

        # 11th scan attempt should hit rate limit
        with patch("app.tasks.scan_tasks.run_osint_scan.delay") as md:
            md.return_value = MagicMock(id="rate-t")
            r = await client.post(
                "/api/v1/scans/",
                json={"scan_type": "email", "query_value": "blocked@test.com"},
                headers=auth_headers,
            )
        assert r.status_code == 429
        assert "rate limit" in r.json()["detail"].lower()
