"""
DataShield OSINT - Takedown & Monitoring Models
Removal requests, tracking, monitoring configuration

Mapper note:
  TakedownRequest.finding and MonitorConfig.finding point back to Finding
  using foreign_keys + overlaps to prevent circular mapper init with scan.py.
  Finding's side declares the relationship via primaryjoin without back_populates.
"""
import uuid
import enum
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer,
    ForeignKey, Enum as SAEnum, JSON, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class TakedownStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    REMOVED = "removed"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    FAILED = "failed"


class TakedownTemplateType(str, enum.Enum):
    PRIVACY_REMOVAL = "privacy_removal"
    GDPR_REMOVAL = "gdpr_removal"
    RIGHT_TO_BE_FORGOTTEN = "right_to_be_forgotten"
    DMCA_PERSONAL_DATA = "dmca_personal_data"


class MonitorInterval(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ── Models ────────────────────────────────────────────────────────────────────

class TakedownRequest(Base):
    __tablename__ = "takedown_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)

    template_type = Column(SAEnum(TakedownTemplateType), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    legal_references = Column(JSON, default=list)

    target_url = Column(Text, nullable=False)
    target_domain = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    abuse_email = Column(String(255), nullable=True)
    privacy_officer_email = Column(String(255), nullable=True)
    contact_form_url = Column(Text, nullable=True)
    whois_registrar = Column(String(255), nullable=True)

    status = Column(SAEnum(TakedownStatus), default=TakedownStatus.PENDING)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)

    follow_up_count = Column(Integer, default=0)
    next_follow_up_at = Column(DateTime(timezone=True), nullable=True)
    response_received = Column(Text, nullable=True)
    escalation_reason = Column(Text, nullable=True)
    complaint_filed = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="takedown_requests")
    status_history = relationship(
        "TakedownStatusHistory",
        back_populates="takedown",
        cascade="all, delete-orphan",
    )
    # Cross-module: Finding is in scan.py — use foreign_keys, no back_populates
    finding = relationship(
        "Finding",
        foreign_keys=[finding_id],
        lazy="select",
        overlaps="takedown_request",  # matches Finding.takedown_request overlaps=
    )

    __table_args__ = (
        Index("ix_takedown_user_status", "user_id", "status"),
    )


class TakedownStatusHistory(Base):
    __tablename__ = "takedown_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    takedown_id = Column(UUID(as_uuid=True), ForeignKey("takedown_requests.id", ondelete="CASCADE"), nullable=False)
    old_status = Column(SAEnum(TakedownStatus), nullable=True)
    new_status = Column(SAEnum(TakedownStatus), nullable=False)
    note = Column(Text, nullable=True)
    changed_by = Column(String(100), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    takedown = relationship("TakedownRequest", back_populates="status_history")


class MonitorConfig(Base):
    __tablename__ = "monitor_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)

    target_url = Column(Text, nullable=False)
    target_domain = Column(String(255), nullable=False)
    monitor_interval = Column(SAEnum(MonitorInterval), default=MonitorInterval.WEEKLY)

    is_active = Column(Boolean, default=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    next_check_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0)
    last_status = Column(String(50), nullable=True)
    last_snapshot_url = Column(String(500), nullable=True)

    alert_on_reappear = Column(Boolean, default=True)
    alert_on_new_leak = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="monitors")
    check_history = relationship(
        "MonitorCheckHistory",
        back_populates="monitor",
        cascade="all, delete-orphan",
    )
    # Cross-module: Finding is in scan.py — use foreign_keys, no back_populates
    finding = relationship(
        "Finding",
        foreign_keys=[finding_id],
        lazy="select",
        overlaps="monitor",  # matches Finding.monitor overlaps=
    )


class MonitorCheckHistory(Base):
    __tablename__ = "monitor_check_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id = Column(UUID(as_uuid=True), ForeignKey("monitor_configs.id", ondelete="CASCADE"), nullable=False)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), nullable=False)
    http_status_code = Column(Integer, nullable=True)
    page_accessible = Column(Boolean, nullable=True)
    data_still_present = Column(Boolean, nullable=True)
    snapshot_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    monitor = relationship("MonitorConfig", back_populates="check_history")


class CybercrimeComplaint(Base):
    __tablename__ = "cybercrime_complaints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    incident_summary = Column(Text, nullable=False)
    affected_data = Column(JSON, default=list)
    exposure_timeline = Column(JSON, default=list)
    jurisdiction = Column(String(100), nullable=True)
    authority_name = Column(String(255), nullable=True)
    authority_url = Column(String(500), nullable=True)
    package_url = Column(String(500), nullable=True)
    finding_ids = Column(JSON, default=list)

    is_submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reference_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="info")
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)

    email_sent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    push_sent = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )
