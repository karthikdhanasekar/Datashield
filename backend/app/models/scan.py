"""
DataShield OSINT - Scan & Finding Models
Scan requests, OSINT findings, evidence, exposure classification

Mapper note:
  Finding.takedown_request and Finding.monitor use viewonly=False, lazy="select"
  with no back_populates on the Finding side to avoid circular mapper
  initialization between scan.py and takedown.py.
  The owning side (TakedownRequest.finding, MonitorConfig.finding) declares
  back_populates and is the single source of truth.
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer, Float,
    ForeignKey, Enum as SAEnum, JSON, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanType(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    NAME = "name"
    USERNAME = "username"
    AADHAAR = "aadhaar"
    PAN = "pan"
    PASSPORT = "passport"
    ADDRESS = "address"
    SOCIAL_PROFILE = "social_profile"
    FULL = "full"


class SeverityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingType(str, enum.Enum):
    BREACH = "breach"
    SOCIAL_MEDIA = "social_media"
    SEARCH_ENGINE = "search_engine"
    DOCUMENT = "document"
    DARK_WEB_INDICATOR = "dark_web_indicator"
    WHOIS = "whois"
    PASTE_SITE = "paste_site"
    FORUM = "forum"
    NEWS = "news"


# ── Models ────────────────────────────────────────────────────────────────────

class ScanRequest(Base):
    __tablename__ = "scan_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    scan_type = Column(SAEnum(ScanType), nullable=False)
    query_value = Column(String(500), nullable=False)
    query_masked = Column(String(500), nullable=True)

    status = Column(SAEnum(ScanStatus), default=ScanStatus.PENDING)
    celery_task_id = Column(String(100), nullable=True)
    progress = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    total_findings = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    exposure_score = Column(Float, default=0.0)

    modules_run = Column(JSON, default=list)
    modules_completed = Column(JSON, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships — all within same module, safe
    user = relationship("User", back_populates="scans")
    findings = relationship("Finding", back_populates="scan", cascade="all, delete-orphan")
    report = relationship("EvidenceReport", back_populates="scan", uselist=False)

    __table_args__ = (
        Index("ix_scan_requests_user_status", "user_id", "status"),
        Index("ix_scan_requests_created", "created_at"),
    )


class Finding(Base):
    __tablename__ = "findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scan_requests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    finding_type = Column(SAEnum(FindingType), nullable=False)
    source_url = Column(Text, nullable=True)
    source_domain = Column(String(255), nullable=True)
    source_title = Column(Text, nullable=True)
    source_name = Column(String(255), nullable=True)

    severity = Column(SAEnum(SeverityLevel), nullable=False, default=SeverityLevel.LOW)
    risk_score = Column(Float, default=0.0)
    description = Column(Text, nullable=True)
    exposed_data_types = Column(JSON, default=list)

    identity_theft_risk = Column(Boolean, default=False)
    financial_risk = Column(Boolean, default=False)
    reputation_risk = Column(Boolean, default=False)
    credential_exposure = Column(Boolean, default=False)
    government_id_exposure = Column(Boolean, default=False)

    raw_data = Column(JSON, nullable=True)
    snippet = Column(Text, nullable=True)

    screenshot_url = Column(String(500), nullable=True)
    evidence_hash = Column(String(64), nullable=True)

    is_verified = Column(Boolean, default=False)
    is_false_positive = Column(Boolean, default=False)
    is_removed = Column(Boolean, default=False)
    removed_at = Column(DateTime(timezone=True), nullable=True)

    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Relationships within scan module (safe — same file) ───────────────────
    scan = relationship("ScanRequest", back_populates="findings")
    user = relationship("User", back_populates="findings")

    # ── Cross-module relationships (takedown.py) ──────────────────────────────
    # NOTE: Do NOT use back_populates here to avoid circular mapper init.
    # The owning side is TakedownRequest.finding and MonitorConfig.finding.
    # Use primaryjoin + foreign_keys + overlaps to suppress SA warnings.
    takedown_request = relationship(
        "TakedownRequest",
        primaryjoin="Finding.id == foreign(TakedownRequest.finding_id)",
        uselist=False,
        lazy="select",
        overlaps="finding",
        viewonly=False,
    )
    monitor = relationship(
        "MonitorConfig",
        primaryjoin="Finding.id == foreign(MonitorConfig.finding_id)",
        uselist=False,
        lazy="select",
        overlaps="finding",
        viewonly=False,
    )

    __table_args__ = (
        Index("ix_findings_user_severity", "user_id", "severity"),
        Index("ix_findings_scan", "scan_id"),
        Index("ix_findings_source_domain", "source_domain"),
    )


class EvidenceReport(Base):
    __tablename__ = "evidence_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scan_requests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    report_title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    finding_count = Column(Integer, default=0)

    pdf_url = Column(String(500), nullable=True)
    json_url = Column(String(500), nullable=True)
    csv_url = Column(String(500), nullable=True)
    package_url = Column(String(500), nullable=True)
    report_hash = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    scan = relationship("ScanRequest", back_populates="report")
