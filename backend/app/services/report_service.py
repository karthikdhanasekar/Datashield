"""
DataShield OSINT - Report Service
Evidence report and complaint package generation (PDF, JSON, CSV)
"""
import io
import json
import csv
import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from structlog import get_logger

logger = get_logger(__name__)


async def generate_evidence_report(scan, findings, user) -> dict:
    """
    Generate a complete evidence report package for a scan.
    Returns URLs to uploaded PDF, JSON, and CSV files.
    """
    report_data = _build_report_data(scan, findings, user)

    pdf_bytes = _generate_pdf_report(report_data)
    json_bytes = _generate_json_report(report_data)
    csv_bytes = _generate_csv_report(findings)

    # Upload to MinIO
    pdf_url = await _upload_to_storage(pdf_bytes, f"reports/{scan.id}/evidence_report.pdf", "application/pdf")
    json_url = await _upload_to_storage(json_bytes, f"reports/{scan.id}/evidence_report.json", "application/json")
    csv_url = await _upload_to_storage(csv_bytes, f"reports/{scan.id}/evidence_report.csv", "text/csv")

    report_hash = hashlib.sha256(pdf_bytes).hexdigest()

    return {
        "pdf_url": pdf_url,
        "json_url": json_url,
        "csv_url": csv_url,
        "report_hash": report_hash,
    }


async def generate_complaint_package(complaint, findings, user) -> Optional[str]:
    """Generate a downloadable cybercrime complaint package."""
    try:
        report_data = {
            "complaint_id": str(complaint.id),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_subject": {
                "name": user.full_name or "N/A",
                "email": user.email,
            },
            "incident_summary": complaint.incident_summary,
            "jurisdiction": complaint.jurisdiction,
            "authority": complaint.authority_name,
            "affected_data": complaint.affected_data,
            "exposure_timeline": complaint.exposure_timeline,
            "findings": [
                {
                    "id": str(f.id),
                    "type": f.finding_type.value,
                    "source": f.source_domain,
                    "url": f.source_url,
                    "severity": f.severity.value,
                    "discovered": str(f.discovered_at),
                    "data_types": f.exposed_data_types,
                }
                for f in findings
            ],
        }

        json_bytes = json.dumps(report_data, indent=2, default=str).encode("utf-8")
        url = await _upload_to_storage(
            json_bytes,
            f"complaints/{complaint.id}/complaint_package.json",
            "application/json",
        )
        return url
    except Exception as e:
        logger.error("Complaint package generation failed", error=str(e))
        return None


def _build_report_data(scan, findings, user) -> dict:
    return {
        "report_title": f"DataShield OSINT — Evidence Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scan_id": str(scan.id),
        "scan_type": scan.scan_type.value,
        "data_subject": user.email,
        "exposure_score": scan.exposure_score,
        "summary": {
            "total_findings": scan.total_findings,
            "critical": scan.critical_count,
            "high": scan.high_count,
            "medium": scan.medium_count,
            "low": scan.low_count,
        },
        "findings": [
            {
                "id": str(f.id),
                "type": f.finding_type.value,
                "severity": f.severity.value,
                "risk_score": f.risk_score,
                "source_url": f.source_url,
                "source_domain": f.source_domain,
                "source_title": f.source_title,
                "description": f.description,
                "exposed_data": f.exposed_data_types,
                "snippet": f.snippet,
                "discovered_at": str(f.discovered_at),
            }
            for f in findings
        ],
    }


def _generate_pdf_report(data: dict) -> bytes:
    """Generate a PDF report. Uses reportlab for basic formatting."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#0ea5e9"))
        story.append(Paragraph("DataShield OSINT — Evidence Report", title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Meta
        story.append(Paragraph(f"Generated: {data['generated_at']}", styles["Normal"]))
        story.append(Paragraph(f"Scan ID: {data['scan_id']}", styles["Normal"]))
        story.append(Paragraph(f"Exposure Score: {data['exposure_score']}/100", styles["Normal"]))
        story.append(Spacer(1, 0.3 * inch))

        # Summary table
        story.append(Paragraph("Exposure Summary", styles["Heading2"]))
        summary = data["summary"]
        table_data = [
            ["Severity", "Count"],
            ["Critical", summary["critical"]],
            ["High", summary["high"]],
            ["Medium", summary["medium"]],
            ["Low", summary["low"]],
            ["Total", summary["total_findings"]],
        ]
        t = Table(table_data, colWidths=[2 * inch, 1.5 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

        # Findings
        story.append(Paragraph("Findings Detail", styles["Heading2"]))
        severity_colors = {
            "critical": "#ef4444", "high": "#f97316",
            "medium": "#eab308", "low": "#22c55e",
        }
        for f in data["findings"]:
            color = severity_colors.get(f["severity"], "#64748b")
            sev_style = ParagraphStyle("sev", parent=styles["Normal"], textColor=colors.HexColor(color))
            story.append(Paragraph(f"[{f['severity'].upper()}] {f['source_domain'] or 'Unknown'}", sev_style))
            story.append(Paragraph(f"URL: {f['source_url'] or 'N/A'}", styles["Normal"]))
            if f.get("description"):
                story.append(Paragraph(f["description"], styles["Normal"]))
            story.append(Spacer(1, 0.15 * inch))

        doc.build(story)
        return buffer.getvalue()
    except Exception as e:
        logger.error("PDF generation failed", error=str(e))
        return json.dumps(data, default=str).encode("utf-8")


def _generate_json_report(data: dict) -> bytes:
    return json.dumps(data, indent=2, default=str).encode("utf-8")


def _generate_csv_report(findings) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Type", "Severity", "Risk Score", "Source Domain",
        "Source URL", "Discovered At", "Data Types", "Description",
    ])
    for f in findings:
        writer.writerow([
            str(f.id), f.finding_type.value, f.severity.value,
            f.risk_score, f.source_domain or "", f.source_url or "",
            str(f.discovered_at),
            ",".join(f.exposed_data_types or []),
            (f.description or "")[:200],
        ])
    return output.getvalue().encode("utf-8")


async def _upload_to_storage(content: bytes, path: str, content_type: str) -> Optional[str]:
    """Upload file to MinIO/S3 storage. Returns public URL."""
    try:
        from minio import Minio
        from app.core.config import settings
        import io

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )

        # Ensure bucket exists
        if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
            client.make_bucket(settings.MINIO_BUCKET_NAME)

        client.put_object(
            settings.MINIO_BUCKET_NAME,
            path,
            io.BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
        return f"http://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{path}"
    except Exception as e:
        logger.error("Storage upload failed", path=path, error=str(e))
        return None
