"""
DataShield OSINT - Admin API
User management, analytics, system configuration
"""
from typing import Annotated, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.database import get_db
from app.api.deps import require_role, get_pagination
from app.models.user import User, UserStatus, UserRole, AuditLog
from app.models.scan import ScanRequest, Finding, ScanStatus
from app.models.takedown import TakedownRequest, TakedownStatus

router = APIRouter(prefix="/admin", tags=["Admin"])
AdminRequired = Depends(require_role("admin"))


@router.get("/users")
async def list_users(
    admin: Annotated[User, AdminRequired],
    db: Annotated[AsyncSession, Depends(get_db)],
    role: Optional[str] = None,
    status: Optional[str] = None,
    pagination: dict = Depends(get_pagination),
):
    """List all users with optional filters."""
    query = select(User)
    if role:
        query = query.where(User.role == UserRole(role))
    if status:
        query = query.where(User.status == UserStatus(status))

    total = (await db.execute(
        select(func.count()).select_from(User)
    )).scalar_one()

    result = await db.execute(
        query.order_by(desc(User.created_at))
        .offset(pagination["offset"]).limit(pagination["page_size"])
    )
    users = result.scalars().all()

    return {
        "items": [
            {
                "id": str(u.id), "email": u.email, "full_name": u.full_name,
                "role": u.role.value, "status": u.status.value,
                "mfa_enabled": u.mfa_enabled, "email_verified": u.email_verified,
                "created_at": str(u.created_at), "last_login_at": str(u.last_login_at) if u.last_login_at else None,
            }
            for u in users
        ],
        "total": total,
        "page": pagination["page"],
        "page_size": pagination["page_size"],
    }


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    new_status: str,
    admin: Annotated[User, AdminRequired],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Suspend, activate, or deactivate a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.status = UserStatus(new_status)
    await db.commit()
    return {"message": f"User status updated to {new_status}"}


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    new_role: str,
    admin: Annotated[User, AdminRequired],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change a user's role."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.role = UserRole(new_role)
    await db.commit()
    return {"message": f"User role updated to {new_role}"}


@router.get("/analytics/overview")
async def get_analytics_overview(
    admin: Annotated[User, AdminRequired],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Platform-wide analytics overview."""
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    active_users = (await db.execute(
        select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE)
    )).scalar_one()
    total_scans = (await db.execute(select(func.count()).select_from(ScanRequest))).scalar_one()
    total_findings = (await db.execute(select(func.count()).select_from(Finding))).scalar_one()
    active_findings = (await db.execute(
        select(func.count()).select_from(Finding).where(Finding.is_removed == False, Finding.is_false_positive == False)
    )).scalar_one()
    removed_findings = (await db.execute(
        select(func.count()).select_from(Finding).where(Finding.is_removed == True)
    )).scalar_one()
    total_takedowns = (await db.execute(select(func.count()).select_from(TakedownRequest))).scalar_one()
    successful_takedowns = (await db.execute(
        select(func.count()).select_from(TakedownRequest).where(TakedownRequest.status == TakedownStatus.REMOVED)
    )).scalar_one()

    # Scans in last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent_scans = (await db.execute(
        select(func.count()).select_from(ScanRequest).where(ScanRequest.created_at >= thirty_days_ago)
    )).scalar_one()

    removal_rate = round((successful_takedowns / total_takedowns * 100) if total_takedowns > 0 else 0, 1)

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_scans": total_scans,
        "recent_scans_30d": recent_scans,
        "total_findings": total_findings,
        "active_findings": active_findings,
        "removed_findings": removed_findings,
        "total_takedowns": total_takedowns,
        "successful_takedowns": successful_takedowns,
        "removal_success_rate": removal_rate,
    }


@router.get("/analytics/exposure-trends")
async def get_exposure_trends(
    admin: Annotated[User, AdminRequired],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(30, ge=7, le=365),
):
    """Exposure discovery trend over time."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc('day', Finding.discovered_at).label("day"),
            Finding.severity,
            func.count().label("count")
        ).where(Finding.discovered_at >= start_date)
        .group_by("day", Finding.severity)
        .order_by("day")
    )
    rows = result.all()
    return {
        "trends": [
            {"date": str(r.day), "severity": r.severity.value, "count": r.count}
            for r in rows
        ]
    }


@router.get("/audit-logs")
async def get_audit_logs(
    admin: Annotated[User, AdminRequired],
    db: Annotated[AsyncSession, Depends(get_db)],
    action: Optional[str] = None,
    pagination: dict = Depends(get_pagination),
):
    """View platform audit logs."""
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)

    total = (await db.execute(select(func.count()).select_from(AuditLog))).scalar_one()
    result = await db.execute(
        query.order_by(desc(AuditLog.created_at))
        .offset(pagination["offset"]).limit(pagination["page_size"])
    )
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(l.id), "user_id": str(l.user_id) if l.user_id else None,
                "action": l.action, "resource_type": l.resource_type,
                "ip_address": l.ip_address, "status": l.status,
                "details": l.details, "created_at": str(l.created_at),
            }
            for l in logs
        ],
        "total": total,
        "page": pagination["page"],
        "page_size": pagination["page_size"],
    }
