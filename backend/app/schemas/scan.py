"""
DataShield OSINT - Scan Schemas
Request/Response models for scans and findings
"""
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, field_validator
import re


class ScanCreateRequest(BaseModel):
    scan_type: str  # ScanType enum value
    query_value: str
    modules: Optional[List[str]] = None  # Specific modules to run; None = all

    @field_validator("query_value")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Query value cannot be empty")
        if len(v) > 500:
            raise ValueError("Query value too long")
        return v


class ScanStatusResponse(BaseModel):
    id: str
    scan_type: str
    status: str
    progress: int
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    exposure_score: float
    modules_run: List[str]
    modules_completed: List[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class FindingResponse(BaseModel):
    id: str
    finding_type: str
    source_url: Optional[str]
    source_domain: Optional[str]
    source_title: Optional[str]
    source_name: Optional[str]
    severity: str
    risk_score: float
    description: Optional[str]
    exposed_data_types: List[str]
    identity_theft_risk: bool
    financial_risk: bool
    reputation_risk: bool
    credential_exposure: bool
    government_id_exposure: bool
    snippet: Optional[str]
    screenshot_url: Optional[str]
    is_verified: bool
    is_false_positive: bool
    is_removed: bool
    discovered_at: str

    model_config = {"from_attributes": True}


class ScanResultResponse(BaseModel):
    scan: ScanStatusResponse
    findings: List[FindingResponse]
    total: int


class ExposureScoreResponse(BaseModel):
    score: float  # 0-100
    risk_level: str  # "safe" | "low" | "medium" | "high" | "critical"
    breakdown: Dict[str, int]
    recommendations: List[str]


class FindingUpdateRequest(BaseModel):
    is_false_positive: Optional[bool] = None
    is_verified: Optional[bool] = None


class ScanListResponse(BaseModel):
    items: List[ScanStatusResponse]
    total: int
    page: int
    page_size: int


class SearchResultResponse(BaseModel):
    """Response for full-text finding search (Elasticsearch or PostgreSQL)."""
    hits: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    source: str  # "elasticsearch" | "postgresql"
