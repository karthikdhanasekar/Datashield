"""
DataShield OSINT - Takedown & Complaint Schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr


class TakedownCreateRequest(BaseModel):
    finding_id: str
    template_type: str  # TakedownTemplateType enum
    contact_email: Optional[str] = None
    abuse_email: Optional[str] = None
    custom_message: Optional[str] = None  # Additional custom text to append


class TakedownResponse(BaseModel):
    id: str
    finding_id: str
    template_type: str
    subject: str
    body: str
    legal_references: List[str]
    target_url: str
    target_domain: str
    contact_email: Optional[str]
    abuse_email: Optional[str]
    status: str
    sent_at: Optional[str]
    acknowledged_at: Optional[str]
    resolved_at: Optional[str]
    follow_up_count: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TakedownStatusUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = None


class TakedownListResponse(BaseModel):
    items: List[TakedownResponse]
    total: int
    page: int
    page_size: int


class TakedownPreviewResponse(BaseModel):
    subject: str
    body: str
    legal_references: List[str]
    contact_email: Optional[str]
    abuse_email: Optional[str]
    privacy_officer_email: Optional[str]
    contact_form_url: Optional[str]
    whois_registrar: Optional[str]


class ComplaintCreateRequest(BaseModel):
    incident_summary: str
    finding_ids: List[str]
    jurisdiction: Optional[str] = None
    authority_name: Optional[str] = None
    authority_url: Optional[str] = None


class ComplaintResponse(BaseModel):
    id: str
    incident_summary: str
    affected_data: List[str]
    jurisdiction: Optional[str]
    authority_name: Optional[str]
    package_url: Optional[str]
    is_submitted: bool
    submitted_at: Optional[str]
    reference_number: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


class MonitorCreateRequest(BaseModel):
    finding_id: Optional[str] = None
    target_url: str
    monitor_interval: str = "weekly"  # daily | weekly | monthly
    alert_on_reappear: bool = True
    alert_on_new_leak: bool = True


class MonitorResponse(BaseModel):
    id: str
    target_url: str
    target_domain: str
    monitor_interval: str
    is_active: bool
    last_checked_at: Optional[str]
    next_check_at: Optional[str]
    last_status: Optional[str]
    consecutive_failures: int
    created_at: str

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    notification_type: str
    severity: str
    is_read: bool
    read_at: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}
