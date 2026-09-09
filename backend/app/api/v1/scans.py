"""
DataShield OSINT - Scan API
Trigger scans, retrieve results, manage findings
"""
from typing import Annotated, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_active_user, get_pagination
from app.models.user import User
from app.models.scan import ScanRequest, ScanStatus, ScanType, Finding
from app.schemas.scan import (
    ScanCreateRequest, ScanStatusResponse, FindingResponse,
    ScanResultResponse, ScanListResponse, FindingUpdateRequest,
    ExposureScoreResponse, SearchResultResponse,
)
from app.tasks.scan_tasks import run_osint_scan

router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post("/", response_model=ScanStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_scan(
    body: ScanCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Initiate a new OSINT scan.

    Rate limited: max SCAN_RATE_LIMIT_PER_HOUR scans per user per hour.
    """
    # ── Scan rate-limit enforcement ──────────────────────────────────────────
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_count_q = select(func.count()).select_from(ScanRequest).where(
        ScanRequest.user_id == current_user.id,
        ScanRequest.created_at >= one_hour_ago,
    )
    recent_count = (await db.execute(recent_count_q)).scalar_one()
    if recent_count >= settings.SCAN_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Scan rate limit exceeded: maximum {settings.SCAN_RATE_LIMIT_PER_HOUR} "
                "scans per hour. Please wait before starting a new scan."
            ),
        )

    # Validate scan type
    try:
        scan_type = ScanType(body.scan_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid scan type: {body.scan_type}")

    # Mask sensitive values for display
    query_masked = _mask_query(body.query_value, scan_type)

    # Default modules
    modules = body.modules or ["search_engine", "breach", "social_media", "document"]

    scan = ScanRequest(
        user_id=current_user.id,
        scan_type=scan_type,
        query_value=body.query_value,
        query_masked=query_masked,
        status=ScanStatus.PENDING,
        modules_run=modules,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    # Dispatch Celery task
    task = run_osint_scan.delay(str(scan.id), body.query_value, scan_type.value, modules)
    scan.celery_task_id = task.id
    await db.commit()

    return _scan_to_response(scan)


@router.get("/", response_model=ScanListResponse)
async def list_scans(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Optional[str] = Query(None, alias="status"),
    pagination: dict = Depends(get_pagination),
):
    """List all scans for the current user."""
    query = select(ScanRequest).where(ScanRequest.user_id == current_user.id)

    if status_filter:
        try:
            query = query.where(ScanRequest.status == ScanStatus(status_filter))
        except ValueError:
            pass

    total_query = select(func.count()).select_from(ScanRequest).where(
        ScanRequest.user_id == current_user.id
    )
    total = (await db.execute(total_query)).scalar_one()

    query = query.order_by(desc(ScanRequest.created_at)).offset(pagination["offset"]).limit(pagination["page_size"])
    result = await db.execute(query)
    scans = result.scalars().all()

    return ScanListResponse(
        items=[_scan_to_response(s) for s in scans],
        total=total,
        page=pagination["page"],
        page_size=pagination["page_size"],
    )


@router.get("/search", response_model=SearchResultResponse)
async def search_findings(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str = Query(..., min_length=1, max_length=200, description="Full-text search query"),
    severity: Optional[str] = Query(None, description="Filter by severity: low|medium|high|critical"),
    finding_type: Optional[str] = Query(None, description="Filter by finding type"),
    pagination: dict = Depends(get_pagination),
):
    """
    Full-text search across all findings.
    Tries Elasticsearch first; falls back to PostgreSQL ILIKE when ES is unavailable.

    Example: GET /api/v1/scans/search?q=gmail&severity=high

    NOTE: This route must be declared BEFORE /{scan_id} to avoid FastAPI
    matching the literal string "search" as a scan UUID.
    """
    # ── Try Elasticsearch first ──────────────────────────────────────────────
    try:
        from app.services.elasticsearch_service import search_findings as es_search
        result = await es_search(
            user_id=str(current_user.id),
            query=q,
            severity=severity,
            finding_type=finding_type,
            page=pagination["page"],
            page_size=pagination["page_size"],
        )
        # ES client returns None hits list when not available — check total
        if result.get("hits") is not None:
            return SearchResultResponse(
                hits=result["hits"],
                total=result["total"],
                page=pagination["page"],
                page_size=pagination["page_size"],
                source="elasticsearch",
            )
    except Exception:
        pass  # Fall through to PostgreSQL fallback

    # ── PostgreSQL ILIKE fallback (always available) ─────────────────────────
    from sqlalchemy import or_

    like_q = f"%{q}%"
    pg_query = (
        select(Finding)
        .where(
            Finding.user_id == current_user.id,
            Finding.is_false_positive == False,  # noqa: E712
            or_(
                Finding.description.ilike(like_q),
                Finding.source_title.ilike(like_q),
                Finding.source_domain.ilike(like_q),
                Finding.snippet.ilike(like_q),
            ),
        )
        .order_by(desc(Finding.risk_score))
    )

    if severity:
        try:
            from app.models.scan import SeverityLevel
            pg_query = pg_query.where(Finding.severity == SeverityLevel(severity))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    if finding_type:
        try:
            from app.models.scan import FindingType
            pg_query = pg_query.where(Finding.finding_type == FindingType(finding_type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid finding type: {finding_type}")

    # Total count
    count_q = select(func.count()).select_from(
        pg_query.with_only_columns(Finding.id).subquery()
    )
    total = (await db.execute(count_q)).scalar_one()

    # Paginated results
    pg_query = pg_query.offset(pagination["offset"]).limit(pagination["page_size"])
    result = await db.execute(pg_query)
    findings = result.scalars().all()

    return SearchResultResponse(
        hits=[_finding_to_hit(f, q) for f in findings],
        total=total,
        page=pagination["page"],
        page_size=pagination["page_size"],
        source="postgresql",
    )


@router.get("/{scan_id}", response_model=ScanResultResponse)
async def get_scan(
    scan_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get scan status and all findings."""
    result = await db.execute(
        select(ScanRequest).where(
            ScanRequest.id == scan_id,
            ScanRequest.user_id == current_user.id,
        )
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")

    findings_result = await db.execute(
        select(Finding).where(Finding.scan_id == scan_id)
        .order_by(desc(Finding.risk_score))
    )
    findings = findings_result.scalars().all()

    return ScanResultResponse(
        scan=_scan_to_response(scan),
        findings=[_finding_to_response(f) for f in findings],
        total=len(findings),
    )


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan(
    scan_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a scan and all its data."""
    result = await db.execute(
        select(ScanRequest).where(
            ScanRequest.id == scan_id,
            ScanRequest.user_id == current_user.id,
        )
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    await db.delete(scan)
    await db.commit()


@router.patch("/findings/{finding_id}", response_model=FindingResponse)
async def update_finding(
    finding_id: str,
    body: FindingUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark a finding as false positive or verified."""
    result = await db.execute(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.user_id == current_user.id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    if body.is_false_positive is not None:
        finding.is_false_positive = body.is_false_positive
    if body.is_verified is not None:
        finding.is_verified = body.is_verified

    await db.commit()
    await db.refresh(finding)
    return _finding_to_response(finding)


@router.get("/dashboard/exposure-score", response_model=ExposureScoreResponse)
async def get_exposure_score(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the user's current overall exposure score and risk breakdown."""
    # Count active findings by severity
    counts = {}
    for severity in ["critical", "high", "medium", "low"]:
        q = select(func.count()).select_from(Finding).where(
            Finding.user_id == current_user.id,
            Finding.is_false_positive == False,
            Finding.is_removed == False,
            Finding.severity == severity,
        )
        counts[severity] = (await db.execute(q)).scalar_one()

    # Weighted score: critical=40, high=20, medium=8, low=2
    score = min(
        counts.get("critical", 0) * 40 +
        counts.get("high", 0) * 20 +
        counts.get("medium", 0) * 8 +
        counts.get("low", 0) * 2,
        100,
    )

    risk_level = (
        "critical" if score >= 80 else
        "high" if score >= 50 else
        "medium" if score >= 25 else
        "low" if score >= 5 else
        "safe"
    )

    recommendations = _get_recommendations(counts, risk_level)

    return ExposureScoreResponse(
        score=score,
        risk_level=risk_level,
        breakdown=counts,
        recommendations=recommendations,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mask_query(value: str, scan_type: ScanType) -> str:
    """Mask sensitive identifiers for display."""
    if scan_type in (ScanType.AADHAAR, ScanType.PAN, ScanType.PASSPORT):
        return "*" * (len(value) - 4) + value[-4:]
    if scan_type == ScanType.PHONE:
        return value[:3] + "*" * (len(value) - 6) + value[-3:]
    return value


def _finding_to_hit(finding: Finding, query: str) -> dict:
    """Convert a Finding ORM object to an ES-compatible hit dict."""
    # Simple highlight: wrap matched fragments in <em> tags
    highlights: dict = {}
    q_lower = query.lower()
    for field in ("description", "snippet"):
        text = getattr(finding, field, "") or ""
        if q_lower in text.lower():
            idx = text.lower().find(q_lower)
            start = max(0, idx - 60)
            end = min(len(text), idx + len(query) + 60)
            fragment = text[start:end]
            highlights[field] = [fragment]
    return {
        **_finding_to_response(finding).__dict__,
        "highlights": highlights,
    }


def _scan_to_response(scan: ScanRequest) -> ScanStatusResponse:
    return ScanStatusResponse(
        id=str(scan.id),
        scan_type=scan.scan_type.value,
        status=scan.status.value,
        progress=scan.progress,
        total_findings=scan.total_findings,
        critical_count=scan.critical_count,
        high_count=scan.high_count,
        medium_count=scan.medium_count,
        low_count=scan.low_count,
        exposure_score=scan.exposure_score,
        modules_run=scan.modules_run or [],
        modules_completed=scan.modules_completed or [],
        created_at=str(scan.created_at),
        started_at=str(scan.started_at) if scan.started_at else None,
        completed_at=str(scan.completed_at) if scan.completed_at else None,
        error_message=scan.error_message,
    )


def _finding_to_response(finding: Finding) -> FindingResponse:
    return FindingResponse(
        id=str(finding.id),
        finding_type=finding.finding_type.value,
        source_url=finding.source_url,
        source_domain=finding.source_domain,
        source_title=finding.source_title,
        source_name=finding.source_name,
        severity=finding.severity.value,
        risk_score=finding.risk_score,
        description=finding.description,
        exposed_data_types=finding.exposed_data_types or [],
        identity_theft_risk=finding.identity_theft_risk,
        financial_risk=finding.financial_risk,
        reputation_risk=finding.reputation_risk,
        credential_exposure=finding.credential_exposure,
        government_id_exposure=finding.government_id_exposure,
        snippet=finding.snippet,
        screenshot_url=finding.screenshot_url,
        is_verified=finding.is_verified,
        is_false_positive=finding.is_false_positive,
        is_removed=finding.is_removed,
        discovered_at=str(finding.discovered_at),
    )


def _get_recommendations(counts: dict, risk_level: str) -> list:
    recs = []
    if counts.get("critical", 0) > 0:
        recs.append("Immediately request removal of critical exposures — these carry identity theft risk.")
    if counts.get("high", 0) > 0:
        recs.append("File GDPR/privacy removal requests for high-severity findings.")
    if counts.get("medium", 0) > 0:
        recs.append("Review and monitor medium-severity findings for escalation.")
    if risk_level in ("high", "critical"):
        recs.append("Consider enabling continuous monitoring on all active findings.")
        recs.append("Review your social media privacy settings.")
    if risk_level == "safe":
        recs.append("No exposures found. Enable monitoring to stay protected.")
    recs.append("Enable MFA on all accounts where possible.")
    recs.append("Use a password manager to ensure unique passwords per service.")
    return recs
