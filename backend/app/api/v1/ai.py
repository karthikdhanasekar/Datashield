"""
DataShield OSINT - AI Privacy Advisor API
"""
from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.scan import Finding, ScanRequest, ScanStatus
from app.services.ai_advisor import get_ai_advice, analyze_findings

router = APIRouter(prefix="/ai", tags=["AI Advisor"])


class ChatRequest(BaseModel):
    message: str
    include_context: bool = True


class ChatResponse(BaseModel):
    reply: str
    context_used: bool


class AnalyzeRequest(BaseModel):
    scan_id: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_advisor(
    body: ChatRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Chat with the AI Privacy Advisor."""
    context = None
    if body.include_context:
        context = await _get_user_context(db, current_user)

    reply = await get_ai_advice(body.message, context)
    return ChatResponse(reply=reply, context_used=context is not None)


@router.post("/analyze")
async def analyze_scan(
    body: AnalyzeRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate an AI analysis of scan findings."""
    if body.scan_id:
        result = await db.execute(
            select(Finding).where(
                Finding.scan_id == body.scan_id,
                Finding.user_id == current_user.id,
            )
        )
    else:
        # Analyze all active findings
        result = await db.execute(
            select(Finding).where(
                Finding.user_id == current_user.id,
                Finding.is_false_positive == False,
                Finding.is_removed == False,
            ).limit(50)
        )

    findings = result.scalars().all()
    findings_data = [
        {
            "severity": f.severity.value,
            "finding_type": f.finding_type.value,
            "source_domain": f.source_domain,
            "exposed_data_types": f.exposed_data_types or [],
        }
        for f in findings
    ]

    analysis = await analyze_findings(findings_data)
    return {"analysis": analysis, "findings_analyzed": len(findings)}


async def _get_user_context(db, user: User) -> dict:
    from sqlalchemy import func
    from app.models.scan import SeverityLevel

    counts = {}
    for sev in ["critical", "high", "medium", "low"]:
        q = select(func.count()).select_from(Finding).where(
            Finding.user_id == user.id,
            Finding.is_false_positive == False,
            Finding.is_removed == False,
            Finding.severity == sev,
        )
        counts[sev] = (await db.execute(q)).scalar_one()

    total = sum(counts.values())
    score = min(
        counts.get("critical", 0) * 40 + counts.get("high", 0) * 20 +
        counts.get("medium", 0) * 8 + counts.get("low", 0) * 2, 100
    )
    risk_level = (
        "critical" if score >= 80 else "high" if score >= 50 else
        "medium" if score >= 25 else "low" if score >= 5 else "safe"
    )

    return {
        "exposure_score": score,
        "total_findings": total,
        "critical_count": counts.get("critical", 0),
        "high_count": counts.get("high", 0),
        "risk_level": risk_level,
    }
