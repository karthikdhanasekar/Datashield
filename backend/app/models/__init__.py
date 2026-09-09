"""
DataShield OSINT - Models Package
Import order matters: user → scan → takedown (cross-module FK direction).
SQLAlchemy mapper initialisation is deferred so explicit ordering here
prevents the circular mapper cycle between Finding ↔ TakedownRequest.
"""
# 1. Base models with no cross-module deps
from app.models.user import User, Organization, UserSession, AuditLog  # noqa: F401

# 2. Scan models (Finding FK → User only)
from app.models.scan import ScanRequest, Finding, EvidenceReport  # noqa: F401

# 3. Takedown models (TakedownRequest FK → Finding; safe to import after scan)
from app.models.takedown import (  # noqa: F401
    TakedownRequest,
    TakedownStatusHistory,
    MonitorConfig,
    MonitorCheckHistory,
    CybercrimeComplaint,
    Notification,
)

__all__ = [
    "User", "Organization", "UserSession", "AuditLog",
    "ScanRequest", "Finding", "EvidenceReport",
    "TakedownRequest", "TakedownStatusHistory",
    "MonitorConfig", "MonitorCheckHistory",
    "CybercrimeComplaint", "Notification",
]
