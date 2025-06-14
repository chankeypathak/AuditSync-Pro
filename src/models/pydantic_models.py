from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class ReportType(str, Enum):
    INTERNAL = 'internal'
    SEC = 'sec'
    VENDOR = 'vendor'

class ComparisonType(str, Enum):
    INTERNAL_VS_SEC = 'internal_vs_sec'
    INTERNAL_VS_VENDOR = 'internal_vs_vendor'
    SEC_VS_VENDOR = 'sec_vs_vendor'

class TaskStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'

# Company schemas
class CompanyBase(BaseModel):
    name: str
    ticker: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    cik: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    ticker: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    cik: Optional[str] = None

class CompanyResponse(CompanyBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Audit Report schemas
class AuditReportBase(BaseModel):
    report_type: ReportType
    source: str
    file_name: str
    report_date: datetime
    fiscal_year: int
    fiscal_quarter: Optional[str] = None

class AuditReportCreate(AuditReportBase):
    company_id: UUID

class AuditReportUpdate(BaseModel):
    report_type: Optional[ReportType] = None
    source: Optional[str] = None
    report_date: Optional[datetime] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[str] = None
    status: Optional[str] = None

class AuditReportResponse(AuditReportBase):
    id: UUID
    company_id: UUID
    file_path: str
    file_size: Optional[int] = None
    status: str
    processed_at: Optional[datetime] = None
    key_findings: Optional[Dict[str, Any]] = None
    risk_categories: Optional[List[str]] = None
    compliance_scores: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Comparison schemas
class ComparisonBase(BaseModel):
    comparison_type: ComparisonType

class ComparisonCreate(ComparisonBase):
    company_id: UUID
    source_report_id: UUID
    target_report_id: UUID

class ComparisonResponse(ComparisonBase):
    id: UUID
    company_id: UUID
    source_report_id: UUID
    target_report_id: UUID
    status: str
    similarity_score: Optional[float] = None
    key_differences: Optional[Dict[str, Any]] = None
    risk_alignment: Optional[Dict[str, Any]] = None
    compliance_gaps: Optional[Dict[str, Any]] = None
    recommendations: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    role: str = 'analyst'

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Task schemas
class TaskCreate(BaseModel):
    task_type: str
    config: Dict[str, Any]

class TaskResponse(BaseModel):
    id: UUID
    task_type: str
    status: TaskStatus
    config: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
