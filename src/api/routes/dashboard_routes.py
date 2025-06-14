from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from src.services.dashboard_service import DashboardService
from src.models.schemas import DashboardMetrics, ComplianceScore, RiskAssessment
from src.core.dependencies import get_dashboard_service

router = APIRouter()

@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    company_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """Get dashboard metrics and KPIs"""
    if not date_from:
        date_from = datetime.now() - timedelta(days=30)
    if not date_to:
        date_to = datetime.now()
        
    return await dashboard_service.get_metrics(company_id, date_from, date_to)

@router.get("/compliance-score", response_model=ComplianceScore)
async def get_compliance_score(
    company_id: str,
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """Get compliance score for a company"""
    score = await dashboard_service.get_compliance_score(company_id)
    if not score:
        raise HTTPException(status_code=404, detail="Company not found")
    return score

@router.get("/risk-assessment", response_model=List[RiskAssessment])
async def get_risk_assessment(
    company_id: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = 10,
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """Get risk assessment data"""
    return await dashboard_service.get_risk_assessments(company_id, risk_level, limit)

@router.get("/trends")
async def get_trends(
    metric: str,
    company_id: Optional[str] = None,
    period: str = "30d",
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """Get trend data for metrics"""
    return await dashboard_service.get_trends(metric, company_id, period)
