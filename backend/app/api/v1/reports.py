"""
DataShield OSINT - Reports Download API
Serve evidence reports (PDF, JSON, CSV) from MinIO storage
"""
import csv
import io
import json
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import httpx

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.scan import EvidenceReport, ScanRequest, Finding, SeverityLevel, FindingType
from app.services.report_service import generate_evidence_report

router = APIRouter(prefix="/scans", tags=["Reports"])


@router.get("/{scan_id}/report/{fmt}")
async def download_report(
    scan_id: str,
    fmt: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Download an evidence report in the requested format (pdf, json, csv).
    Generates on-demand if not yet available.
    """
    if fmt not in ("pdf", "json", "csv"):
        raise HTTPException(status_code=400, detail="Format must be pdf, json, or csv")

    # Verify scan belongs to user
    scan_result = await db.execute(
        select(ScanRequest).where(
            ScanRequest.id == scan_id,
            ScanRequest.user_id == current_user.id,
        )
    )
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Check for existing report
    report_result = await db.execute(
        select(EvidenceReport).where(EvidenceReport.scan_id == scan_id)
    )
    report = report_result.scalar_one_or_none()

    url_map = {
        "pdf": report.pdf_url if report else None,
        "json": report.json_url if report else None,
        "csv": report.csv_url if report else None,
    }
    file_url = url_map.get(fmt)

    # Generate on-demand if no stored report
    if not file_url:
        findings_result = await db.execute(
            select(Finding).where(Finding.scan_id == scan_id)
        )
        findings = findings_result.scalars().all()

        report_data = await generate_evidence_report(scan, findings, current_user)
        file_url = report_data.get(f"{fmt}_url")

        # Persist report record
        if not report:
            from app.models.scan import EvidenceReport
            report = EvidenceReport(
                scan_id=scan.id,
                user_id=scan.user_id,
                report_title=f"Evidence Report — {scan.scan_type.value} Scan",
                finding_count=len(findings),
                pdf_url=report_data.get("pdf_url"),
                json_url=report_data.get("json_url"),
                csv_url=report_data.get("csv_url"),
                report_hash=report_data.get("report_hash"),
            )
            db.add(report)
            await db.commit()

    if not file_url:
        raise HTTPException(status_code=503, detail="Report generation failed — storage not configured")

    # Stream file from MinIO
    content_types = {
        "pdf": "application/pdf",
        "json": "application/json",
        "csv": "text/csv",
    }
    filenames = {
        "pdf": f"datashield_report_{scan_id[:8]}.pdf",
        "json": f"datashield_report_{scan_id[:8]}.json",
        "csv": f"datashield_report_{scan_id[:8]}.csv",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(file_url)
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch report from storage")

            return Response(
                content=resp.content,
                media_type=content_types[fmt],
                headers={
                    "Content-Disposition": f'attachment; filename="{filenames[fmt]}"',
                    "X-Report-Hash": report.report_hash or "",
                },
            )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Storage service unavailable")


# ── Bulk findings export ──────────────────────────────────────────────────────

@router.get("/findings/export")
async def export_all_findings(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    fmt: str = Query("csv", description="Export format: csv or json"),
    severity: Optional[str] = Query(None, description="Filter by severity: low|medium|high|critical"),
    include_false_positives: bool = Query(False, description="Include false positive findings"),
    include_removed: bool = Query(False, description="Include already-removed findings"),
):
    """
    Export ALL findings for the current user across all scans.

    Supports CSV and JSON formats.
    Optional filters: severity, include_false_positives, include_removed.

    Example:
      GET /api/v1/scans/findings/export?fmt=csv&severity=high
      GET /api/v1/scans/findings/export?fmt=json&include_false_positives=true
    """
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="Format must be csv or json")

    # Build query with optional filters
    query = (
        select(Finding)
        .where(Finding.user_id == current_user.id)
        .order_by(desc(Finding.risk_score), desc(Finding.discovered_at))
    )

    if not include_false_positives:
        query = query.where(Finding.is_false_positive == False)  # noqa: E712
    if not include_removed:
        query = query.where(Finding.is_removed == False)  # noqa: E712

    if severity:
        try:
            query = query.where(Finding.severity == SeverityLevel(severity))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    result = await db.execute(query)
    findings = result.scalars().all()

    if not findings:
        raise HTTPException(status_code=404, detail="No findings match the given filters")

    if fmt == "json":
        return _export_json(findings)
    else:
        return _export_csv(findings)


def _export_json(findings: list) -> Response:
    """Serialize all findings to a JSON download."""
    data = [
        {
            "id":                     str(f.id),
            "finding_type":           f.finding_type.value,
            "source_url":             f.source_url,
            "source_domain":          f.source_domain,
            "source_title":           f.source_title,
            "source_name":            f.source_name,
            "severity":               f.severity.value,
            "risk_score":             f.risk_score,
            "description":            f.description,
            "exposed_data_types":     f.exposed_data_types or [],
            "identity_theft_risk":    f.identity_theft_risk,
            "financial_risk":         f.financial_risk,
            "reputation_risk":        f.reputation_risk,
            "credential_exposure":    f.credential_exposure,
            "government_id_exposure": f.government_id_exposure,
            "snippet":                f.snippet,
            "is_verified":            f.is_verified,
            "is_false_positive":      f.is_false_positive,
            "is_removed":             f.is_removed,
            "discovered_at":          str(f.discovered_at),
            "scan_id":                str(f.scan_id),
        }
        for f in findings
    ]
    payload = json.dumps(
        {"total": len(data), "exported_at": _utc_now(), "findings": data},
        indent=2,
        ensure_ascii=False,
    )
    return Response(
        content=payload.encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="datashield_findings.json"',
        },
    )


def _export_csv(findings: list) -> Response:
    """Serialize all findings to a CSV download."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id", "severity", "risk_score", "finding_type",
            "source_domain", "source_url", "source_title",
            "exposed_data_types", "description", "snippet",
            "identity_theft_risk", "financial_risk", "reputation_risk",
            "credential_exposure", "government_id_exposure",
            "is_verified", "is_false_positive", "is_removed",
            "discovered_at", "scan_id",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for f in findings:
        writer.writerow({
            "id":                     str(f.id),
            "severity":               f.severity.value,
            "risk_score":             f.risk_score,
            "finding_type":           f.finding_type.value,
            "source_domain":          f.source_domain or "",
            "source_url":             f.source_url or "",
            "source_title":           (f.source_title or "").replace("\n", " "),
            "exposed_data_types":     ",".join(f.exposed_data_types or []),
            "description":            (f.description or "").replace("\n", " "),
            "snippet":                (f.snippet or "").replace("\n", " ")[:300],
            "identity_theft_risk":    f.identity_theft_risk,
            "financial_risk":         f.financial_risk,
            "reputation_risk":        f.reputation_risk,
            "credential_exposure":    f.credential_exposure,
            "government_id_exposure": f.government_id_exposure,
            "is_verified":            f.is_verified,
            "is_false_positive":      f.is_false_positive,
            "is_removed":             f.is_removed,
            "discovered_at":          str(f.discovered_at),
            "scan_id":                str(f.scan_id),
        })

    return Response(
        content=output.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="datashield_findings.csv"',
        },
    )


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
