from sqlalchemy import Column, String, DateTime, Text, JSON, Float, Integer, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from src.core.database import Base

# Import all models to ensure they're registered
from .models import Company, AuditReport, Comparison, User, AuditTask

# Create custom indexes for better performance
Index('idx_audit_reports_company_type', AuditReport.company_id, AuditReport.report_type)
Index('idx_audit_reports_date_range', AuditReport.report_date, AuditReport.fiscal_year)
Index('idx_comparisons_company_type', Comparison.company_id, Comparison.comparison_type)
Index('idx_comparisons_reports', Comparison.source_report_id, Comparison.target_report_id)

__all__ = ['Company', 'AuditReport', 'Comparison', 'User', 'AuditTask']
