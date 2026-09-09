"""
DataShield OSINT - Takedown & Monitoring API
Removal requests, status tracking, monitoring, complaints
"""
from typing import Annotated, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.database import get_db
from app.api.deps import get_current_active_user, get_pagination
from app.models.user import User
from app.models.scan import Finding
from app.models.takedown import (
    TakedownRequest, TakedownStatus, TakedownTemplateType,
    MonitorConfig, MonitorInterval, CybercrimeComplaint,
    TakedownStatusHistory, Notification
)
from app.schemas.takedown import (
    TakedownCreateRequest, TakedownResponse, TakedownStatusUpdateRequest,
    TakedownListResponse, TakedownPreviewResponse,
    ComplaintCreateRequest, ComplaintResponse,
    MonitorCreateRequest, MonitorResponse, NotificationResponse
)
from app.services.takedown_service import (
    generate_takedown_email, discover_website_contacts
)
from app.services.report_service import generate_complaint_package
from app.tasks.takedown_tasks import send_takedown_request_task

router = APIRouter(tags=["Takedowns & Monitoring"])


# ── Takedown Requests ─────────────────────────────────────────────────────────

takedown_router = APIRouter(prefix="/takedowns")


@takedown_router.post("/preview", response_model=TakedownPreviewResponse)
async def preview_takedown(
    body: TakedownCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Preview a takedown email before sending."""
    result = await db.execute(
        select(Finding).where(Finding.id == body.finding_id, Finding.user_id == current_user.id)
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    template_type = TakedownTemplateType(body.template_type)
    contacts = await discover_website_contacts(finding.source_domain or "")
    email_content = generate_takedown_email(
        template_type=template_type,
        finding=finding,
        user=current_user,
        custom_message=body.custom_message,
    )

    return TakedownPreviewResponse(
        subject=email_content["subject"],
        body=email_content["body"],
        legal_references=email_content["legal_references"],
        contact_email=contacts.get("contact_email") or body.contact_email,
        abuse_email=contacts.get("abuse_email") or body.abuse_email,
        privacy_officer_email=contacts.get("privacy_officer_email"),
        contact_form_url=contacts.get("contact_form_url"),
        whois_registrar=contacts.get("whois_registrar"),
    )


@takedown_router.post("/", response_model=TakedownResponse, status_code=201)
async def create_takedown(
    body: TakedownCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create and send a takedown request for a finding."""
    result = await db.execute(
        select(Finding).where(Finding.id == body.finding_id, Finding.user_id == current_user.id)
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    template_type = TakedownTemplateType(body.template_type)
    contacts = await discover_website_contacts(finding.source_domain or "")
    email_content = generate_takedown_email(template_type, finding, current_user, body.custom_message)

    takedown = TakedownRequest(
        user_id=current_user.id,
        finding_id=finding.id,
        template_type=template_type,
        subject=email_content["subject"],
        body=email_content["body"],
        legal_references=email_content["legal_references"],
        target_url=finding.source_url or "",
        target_domain=finding.source_domain or "",
        contact_email=contacts.get("contact_email") or body.contact_email,
        abuse_email=contacts.get("abuse_email") or body.abuse_email,
        privacy_officer_email=contacts.get("privacy_officer_email"),
        contact_form_url=contacts.get("contact_form_url"),
        whois_registrar=contacts.get("whois_registrar"),
        status=TakedownStatus.PENDING,
    )
    db.add(takedown)
    await db.flush()

    history = TakedownStatusHistory(
        takedown_id=takedown.id,
        new_status=TakedownStatus.PENDING,
        note="Takedown request created",
        changed_by=current_user.email,
    )
    db.add(history)
    await db.commit()
    await db.refresh(takedown)

    # Dispatch send task
    send_takedown_request_task.delay(str(takedown.id))

    return _takedown_to_response(takedown)


@takedown_router.get("/", response_model=TakedownListResponse)
async def list_takedowns(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Optional[str] = Query(None, alias="status"),
    pagination: dict = Depends(get_pagination),
):
    """List all takedown requests for the current user."""
    query = select(TakedownRequest).where(TakedownRequest.user_id == current_user.id)
    if status_filter:
        try:
            query = query.where(TakedownRequest.status == TakedownStatus(status_filter))
        except ValueError:
            pass

    total = (await db.execute(
        select(func.count()).select_from(TakedownRequest).where(TakedownRequest.user_id == current_user.id)
    )).scalar_one()

    result = await db.execute(
        query.order_by(desc(TakedownRequest.created_at))
        .offset(pagination["offset"]).limit(pagination["page_size"])
    )
    items = result.scalars().all()
    return TakedownListResponse(
        items=[_takedown_to_response(t) for t in items],
        total=total,
        page=pagination["page"],
        page_size=pagination["page_size"],
    )


@takedown_router.patch("/{takedown_id}/status", response_model=TakedownResponse)
async def update_takedown_status(
    takedown_id: str,
    body: TakedownStatusUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manually update the status of a takedown request."""
    result = await db.execute(
        select(TakedownRequest).where(
            TakedownRequest.id == takedown_id,
            TakedownRequest.user_id == current_user.id,
        )
    )
    takedown = result.scalar_one_or_none()
    if not takedown:
        raise HTTPException(status_code=404, detail="Takedown request not found.")

    old_status = takedown.status
    takedown.status = TakedownStatus(body.status)

    if body.status == TakedownStatus.REMOVED.value:
        takedown.resolved_at = datetime.now(timezone.utc)
        # Mark finding as removed
        if takedown.finding:
            takedown.finding.is_removed = True
            takedown.finding.removed_at = datetime.now(timezone.utc)

    history = TakedownStatusHistory(
        takedown_id=takedown.id,
        old_status=old_status,
        new_status=takedown.status,
        note=body.note,
        changed_by=current_user.email,
    )
    db.add(history)
    await db.commit()
    await db.refresh(takedown)
    return _takedown_to_response(takedown)


# ── Monitoring ─────────────────────────────────────────────────────────────────

monitor_router = APIRouter(prefix="/monitors")


@monitor_router.post("/", response_model=MonitorResponse, status_code=201)
async def create_monitor(
    body: MonitorCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Set up continuous monitoring for a URL."""
    from urllib.parse import urlparse
    domain = urlparse(body.target_url).netloc or body.target_url

    monitor = MonitorConfig(
        user_id=current_user.id,
        finding_id=body.finding_id,
        target_url=body.target_url,
        target_domain=domain,
        monitor_interval=MonitorInterval(body.monitor_interval),
        alert_on_reappear=body.alert_on_reappear,
        alert_on_new_leak=body.alert_on_new_leak,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return _monitor_to_response(monitor)


@monitor_router.get("/", response_model=list[MonitorResponse])
async def list_monitors(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(MonitorConfig).where(MonitorConfig.user_id == current_user.id)
        .order_by(desc(MonitorConfig.created_at))
    )
    return [_monitor_to_response(m) for m in result.scalars().all()]


@monitor_router.delete("/{monitor_id}", status_code=204)
async def delete_monitor(
    monitor_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(MonitorConfig).where(
            MonitorConfig.id == monitor_id,
            MonitorConfig.user_id == current_user.id,
        )
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found.")
    await db.delete(monitor)
    await db.commit()


# ── Complaints ─────────────────────────────────────────────────────────────────

complaint_router = APIRouter(prefix="/complaints")


@complaint_router.post("/", response_model=ComplaintResponse, status_code=201)
async def create_complaint(
    body: ComplaintCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a cybercrime complaint package."""
    findings = []
    for fid in body.finding_ids:
        r = await db.execute(select(Finding).where(Finding.id == fid, Finding.user_id == current_user.id))
        f = r.scalar_one_or_none()
        if f:
            findings.append(f)

    affected_data = list({dt for f in findings for dt in (f.exposed_data_types or [])})
    exposure_timeline = [
        {"date": str(f.discovered_at), "source": f.source_domain, "severity": f.severity.value}
        for f in findings
    ]

    complaint = CybercrimeComplaint(
        user_id=current_user.id,
        incident_summary=body.incident_summary,
        affected_data=affected_data,
        exposure_timeline=exposure_timeline,
        jurisdiction=body.jurisdiction,
        authority_name=body.authority_name,
        authority_url=body.authority_url,
        finding_ids=body.finding_ids,
    )
    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)

    # Generate downloadable package
    package_url = await generate_complaint_package(complaint, findings, current_user)
    complaint.package_url = package_url
    await db.commit()

    return ComplaintResponse(
        id=str(complaint.id),
        incident_summary=complaint.incident_summary,
        affected_data=complaint.affected_data,
        jurisdiction=complaint.jurisdiction,
        authority_name=complaint.authority_name,
        package_url=complaint.package_url,
        is_submitted=complaint.is_submitted,
        submitted_at=str(complaint.submitted_at) if complaint.submitted_at else None,
        reference_number=complaint.reference_number,
        created_at=str(complaint.created_at),
    )


# ── Notifications ─────────────────────────────────────────────────────────────

notification_router = APIRouter(prefix="/notifications")


@notification_router.get("/", response_model=list[NotificationResponse])
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    unread_only: bool = Query(False),
):
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.is_read == False)
    result = await db.execute(query.order_by(desc(Notification.created_at)).limit(50))
    return [_notif_to_response(n) for n in result.scalars().all()]


@notification_router.post("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if notif:
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        await db.commit()


@notification_router.post("/read-all", status_code=204)
async def mark_all_read(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    for n in result.scalars().all():
        n.is_read = True
        n.read_at = datetime.now(timezone.utc)
    await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _takedown_to_response(t: TakedownRequest) -> TakedownResponse:
    return TakedownResponse(
        id=str(t.id), finding_id=str(t.finding_id),
        template_type=t.template_type.value, subject=t.subject, body=t.body,
        legal_references=t.legal_references or [], target_url=t.target_url,
        target_domain=t.target_domain, contact_email=t.contact_email,
        abuse_email=t.abuse_email, status=t.status.value,
        sent_at=str(t.sent_at) if t.sent_at else None,
        acknowledged_at=str(t.acknowledged_at) if t.acknowledged_at else None,
        resolved_at=str(t.resolved_at) if t.resolved_at else None,
        follow_up_count=t.follow_up_count,
        created_at=str(t.created_at), updated_at=str(t.updated_at),
    )


def _monitor_to_response(m: MonitorConfig) -> MonitorResponse:
    return MonitorResponse(
        id=str(m.id), target_url=m.target_url, target_domain=m.target_domain,
        monitor_interval=m.monitor_interval.value, is_active=m.is_active,
        last_checked_at=str(m.last_checked_at) if m.last_checked_at else None,
        next_check_at=str(m.next_check_at) if m.next_check_at else None,
        last_status=m.last_status, consecutive_failures=m.consecutive_failures,
        created_at=str(m.created_at),
    )


def _notif_to_response(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=str(n.id), title=n.title, message=n.message,
        notification_type=n.notification_type, severity=n.severity,
        is_read=n.is_read, read_at=str(n.read_at) if n.read_at else None,
        resource_type=n.resource_type, resource_id=n.resource_id,
        created_at=str(n.created_at),
    )
