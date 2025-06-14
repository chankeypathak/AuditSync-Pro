from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import List, Optional
import asyncio

from src.services.audit_service import AuditService
from src.models.schemas import AuditReportCreate, AuditReportResponse
from src.core.dependencies import get_audit_service

router = APIRouter()

@router.post("/upload", response_model=AuditReportResponse)
async def upload_audit_report(
    file: UploadFile = File(...),
    report_type: str = "internal",
    company_id: Optional[str] = None,
    audit_service: AuditService = Depends(get_audit_service)
):
    """Upload and process an audit report"""
    try:
        result = await audit_service.process_upload(file, report_type, company_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports", response_model=List[AuditReportResponse])
async def get_audit_reports(
    company_id: Optional[str] = None,
    report_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    audit_service: AuditService = Depends(get_audit_service)
):
    """Get list of audit reports"""
    return await audit_service.get_reports(company_id, report_type, limit, offset)

@router.get("/reports/{report_id}", response_model=AuditReportResponse)
async def get_audit_report(
    report_id: str,
    audit_service: AuditService = Depends(get_audit_service)
):
    """Get specific audit report"""
    report = await audit_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
