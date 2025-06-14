from sqlalchemy import Column, String, DateTime, Text, JSON, Float, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime

from src.core.database import Base

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    ticker = Column(String(10), nullable=True, index=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    cik = Column(String(20), nullable=True, index=True)  # SEC CIK number
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    audit_reports = relationship("AuditReport", back_populates="company")
    comparisons = relationship("Comparison", back_populates="company")

class AuditReport(Base):
    __tablename__ = "audit_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), nullable=False)
    report_type = Column(String(50), nullable=False)  # 'internal', 'sec', 'vendor'
    source = Column(String(100), nullable=False)  # 'internal_audit', 'sec_10k', 'kpmg', etc.
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    file_hash = Column(String(64), nullable=True)  # SHA-256 hash
    
    # Report metadata
    report_date = Column(DateTime(timezone=True), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    fiscal_quarter = Column(String(2), nullable=True)  # Q1, Q2, Q3, Q4
    
    # Processing status
    status = Column(String(20), default='uploaded')  # uploaded, processing, processed, error
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Extracted content
    raw_text = Column(Text, nullable=True)
    structured_data = Column(JSON, nullable=True)
    
    # AI processing results
    embeddings = Column(ARRAY(Float), nullable=True)
    key_findings = Column(JSON, nullable=True)
    risk_categories = Column(ARRAY(String), nullable=True)
    compliance_scores = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship('Company', back_populates='audit_reports')
    comparisons_as_source = relationship('Comparison', foreign_keys='Comparison.source_report_id', back_populates='source_report')
    comparisons_as_target = relationship('Comparison', foreign_keys='Comparison.target_report_id', back_populates='target_report')

class Comparison(Base):
    __tablename__ = 'comparisons'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), nullable=False)
    source_report_id = Column(UUID(as_uuid=True), ForeignKey('audit_reports.id'), nullable=False)
    target_report_id = Column(UUID(as_uuid=True), ForeignKey('audit_reports.id'), nullable=False)
    
    # Comparison metadata
    comparison_type = Column(String(50), nullable=False)  # 'internal_vs_sec', 'internal_vs_vendor', etc.
    status = Column(String(20), default='pending')  # pending, processing, completed, error
    
    # AI comparison results
    similarity_score = Column(Float, nullable=True)  # 0.0 to 1.0
    key_differences = Column(JSON, nullable=True)
    risk_alignment = Column(JSON, nullable=True)
    compliance_gaps = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    
    # Detailed analysis
    section_comparisons = Column(JSON, nullable=True)  # Detailed section-by-section comparison
    discrepancy_analysis = Column(JSON, nullable=True)
    materiality_assessment = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    company = relationship('Company', back_populates='comparisons')
    source_report = relationship('AuditReport', foreign_keys=[source_report_id], back_populates='comparisons_as_source')
    target_report = relationship('AuditReport', foreign_keys=[target_report_id], back_populates='comparisons_as_target')

class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # User role and permissions
    role = Column(String(50), default='analyst')  # admin, manager, analyst, viewer
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # User preferences
    preferences = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

class AuditTask(Base):
    __tablename__ = 'audit_tasks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(50), nullable=False)  # 'comparison', 'analysis', 'report_generation'
    status = Column(String(20), default='pending')  # pending, running, completed, failed
    
    # Task configuration
    config = Column(JSON, nullable=False)
    
    # Task results
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Progress tracking
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    logs = Column(Text, nullable=True)
