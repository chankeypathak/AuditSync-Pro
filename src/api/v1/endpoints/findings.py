"""
Findings and Comparisons API endpoints for AuditSync-Pro
Handles AI-generated findings, document comparisons, and discrepancy analysis
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from src.core.database import get_db_session
from src.core.auth import get_current_user, require_permissions
from src.core.config import get_settings
from src.models.findings import (
    Finding, 
    FindingCategory, 
    FindingSeverity, 
    FindingStatus,
    DocumentComparison,
    ComparisonResult,
    Discrepancy,
    DiscrepancyType,
    RiskLevel
)
from src.models.documents import Document
from src.models.users import User
from src.schemas.findings import (
    FindingCreate,
    FindingUpdate,
    FindingResponse,
    FindingListResponse,
    FindingAnalyticsResponse,
    ComparisonCreate,
    ComparisonResponse,
    ComparisonListResponse,
    ComparisonDetailResponse,
    DiscrepancyResponse,
    RiskAssessmentResponse,
    TrendAnalysisResponse,
    ComplianceScoreResponse,
    FindingSearchRequest,
    BulkFindingUpdateRequest
)
from src.services.findings_service import FindingsService
from src.services.ai_service import AIService
from src.services.risk_service import RiskService
from src.services.notification_service import NotificationService
from src.utils.exceptions import FindingNotFoundError, ComparisonNotFoundError
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Initialize routers
findings_router = APIRouter(prefix="/findings", tags=["findings"])
comparisons_router = APIRouter(prefix="/comparisons", tags=["comparisons"])

# Constants
SEVERITY_PRIORITY = {
    FindingSeverity.CRITICAL: 4,
    FindingSeverity.HIGH: 3,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.LOW: 1
}

COMPLIANCE_FRAMEWORKS = [
    "SOX", "GAAP", "IFRS", "COSO", "ISO27001", "SOC2", "GDPR", "PCAOB"
]


# ==================== FINDINGS ENDPOINTS ====================

@findings_router.post("/", response_model=FindingResponse, status_code=status.HTTP_201_CREATED)
async def create_finding(
    finding_data: FindingCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
    notification_service: NotificationService = Depends(),
) -> FindingResponse:
    """Create a new audit finding"""
    try:
        # Check permissions
        await require_permissions(current_user, "findings:create", resource_id=str(finding_data.company_id))
        
        # Create finding
        finding = await findings_service.create_finding(db, finding_data, current_user.id)
        
        # Send notifications for high/critical findings
        if finding.severity in [FindingSeverity.HIGH, FindingSeverity.CRITICAL]:
            await notification_service.notify_high_risk_finding(finding)
        
        logger.info(f"Finding {finding.id} created by user {current_user.id}")
        
        return FindingResponse.from_orm(finding)
        
    except Exception as e:
        logger.error(f"Error creating finding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create finding: {str(e)}"
        )


@findings_router.get("/{finding_id}", response_model=FindingResponse)
async def get_finding(
    finding_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> FindingResponse:
    """Get finding details by ID"""
    try:
        finding = await findings_service.get_finding_by_id(db, finding_id)
        if not finding:
            raise FindingNotFoundError(f"Finding {finding_id} not found")
        
        await require_permissions(current_user, "findings:read", resource_id=str(finding.company_id))
        
        return FindingResponse.from_orm(finding)
        
    except FindingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding {finding_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving finding {finding_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve finding"
        )


@findings_router.get("/", response_model=FindingListResponse)
async def list_findings(
    company_id: Optional[UUID] = Query(None, description="Filter by company ID"),
    document_id: Optional[UUID] = Query(None, description="Filter by document ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[str] = Query(None, description="Filter by date range start"),
    date_to: Optional[str] = Query(None, description="Filter by date range end"),
    compliance_framework: Optional[str] = Query(None, description="Filter by compliance framework"),
    assigned_to: Optional[UUID] = Query(None, description="Filter by assigned user"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> FindingListResponse:
    """List findings with filtering, sorting, and pagination"""
    try:
        # Build filters
        filters = {
            "company_id": company_id,
            "document_id": document_id,
            "category": category,
            "severity": severity,
            "status": status,
            "compliance_framework": compliance_framework,
            "assigned_to": assigned_to
        }
        
        if date_from:
            filters["date_from"] = datetime.fromisoformat(date_from)
        if date_to:
            filters["date_to"] = datetime.fromisoformat(date_to)
        
        # Get paginated results
        findings, total_count = await findings_service.list_findings(
            db, filters, page, page_size, sort_by, sort_order
        )
        
        # Filter by permissions
        accessible_findings = []
        for finding in findings:
            try:
                await require_permissions(current_user, "findings:read", resource_id=str(finding.company_id))
                accessible_findings.append(FindingResponse.from_orm(finding))
            except:
                continue
        
        return FindingListResponse(
            findings=accessible_findings,
            total_count=len(accessible_findings),
            page=page,
            page_size=page_size,
            total_pages=(len(accessible_findings) + page_size - 1) // page_size,
            filters_applied=filters
        )
        
    except Exception as e:
        logger.error(f"Error listing findings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve findings"
        )


@findings_router.post("/search", response_model=FindingListResponse)
async def search_findings(
    search_request: FindingSearchRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
    ai_service: AIService = Depends(),
) -> FindingListResponse:
    """Semantic search across findings using AI"""
    try:
        # Perform semantic search
        search_results = await ai_service.search_findings(
            query=search_request.query,
            filters={
                "company_ids": search_request.company_ids,
                "categories": search_request.categories,
                "severities": search_request.severities,
                "date_range": {
                    "start": search_request.date_range_start,
                    "end": search_request.date_range_end
                }
            },
            similarity_threshold=search_request.similarity_threshold or 0.7,
            limit=search_request.limit or 20
        )
        
        # Filter by permissions
        accessible_findings = []
        for result in search_results:
            try:
                await require_permissions(current_user, "findings:read", resource_id=str(result.company_id))
                accessible_findings.append(FindingResponse.from_orm(result))
            except:
                continue
        
        return FindingListResponse(
            findings=accessible_findings,
            total_count=len(accessible_findings),
            page=1,
            page_size=len(accessible_findings),
            total_pages=1
        )
        
    except Exception as e:
        logger.error(f"Error searching findings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search findings"
        )


@findings_router.put("/{finding_id}", response_model=FindingResponse)
async def update_finding(
    finding_id: UUID,
    finding_update: FindingUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> FindingResponse:
    """Update an existing finding"""
    try:
        # Check finding exists and permissions
        existing_finding = await findings_service.get_finding_by_id(db, finding_id)
        if not existing_finding:
            raise FindingNotFoundError(f"Finding {finding_id} not found")
        
        await require_permissions(current_user, "findings:update", resource_id=str(existing_finding.company_id))
        
        # Update finding
        updated_finding = await findings_service.update_finding(
            db, finding_id, finding_update, current_user.id
        )
        
        logger.info(f"Finding {finding_id} updated by user {current_user.id}")
        
        return FindingResponse.from_orm(updated_finding)
        
    except FindingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding {finding_id} not found"
        )
    except Exception as e:
        logger.error(f"Error updating finding {finding_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update finding"
        )


@findings_router.post("/bulk-update", response_model=Dict[str, Any])
async def bulk_update_findings(
    bulk_update: BulkFindingUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> Dict[str, Any]:
    """Bulk update multiple findings"""
    try:
        results = await findings_service.bulk_update_findings(
            db, bulk_update.finding_ids, bulk_update.updates, current_user.id
        )
        
        logger.info(f"Bulk update of {len(bulk_update.finding_ids)} findings by user {current_user.id}")
        
        return {
            "updated_count": results["updated_count"],
            "failed_count": results["failed_count"],
            "errors": results["errors"]
        }
        
    except Exception as e:
        logger.error(f"Error in bulk update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk update"
        )


@findings_router.delete("/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_finding(
    finding_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
):
    """Delete a finding"""
    try:
        finding = await findings_service.get_finding_by_id(db, finding_id)
        if not finding:
            raise FindingNotFoundError(f"Finding {finding_id} not found")
        
        await require_permissions(current_user, "findings:delete", resource_id=str(finding.company_id))
        
        await findings_service.delete_finding(db, finding_id)
        
        logger.info(f"Finding {finding_id} deleted by user {current_user.id}")
        
    except FindingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding {finding_id} not found"
        )
    except Exception as e:
        logger.error(f"Error deleting finding {finding_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete finding"
        )


@findings_router.get("/analytics/summary", response_model=FindingAnalyticsResponse)
async def get_findings_analytics(
    company_id: Optional[UUID] = Query(None, description="Filter by company ID"),
    time_period: str = Query("30d", description="Time period (7d, 30d, 90d, 1y)"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> FindingAnalyticsResponse:
    """Get findings analytics and summary statistics"""
    try:
        # Calculate date range
        time_periods = {
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90),
            "1y": timedelta(days=365)
        }
        
        if time_period not in time_periods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid time period. Use: 7d, 30d, 90d, 1y"
            )
        
        end_date = datetime.utcnow()
        start_date = end_date - time_periods[time_period]
        
        # Get analytics
        analytics = await findings_service.get_findings_analytics(
            db, company_id, start_date, end_date
        )
        
        return FindingAnalyticsResponse(**analytics)
        
    except Exception as e:
        logger.error(f"Error getting findings analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )


# ==================== COMPARISONS ENDPOINTS ====================

@comparisons_router.post("/", response_model=ComparisonResponse, status_code=status.HTTP_201_CREATED)
async def create_comparison(
    comparison_data: ComparisonCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
    ai_service: AIService = Depends(),
) -> ComparisonResponse:
    """Create a new document comparison analysis"""
    try:
        # Validate documents exist and user has access
        for doc_id in comparison_data.document_ids:
            # This would check document permissions
            await require_permissions(current_user, "documents:read", resource_id=str(doc_id))
        
        # Create comparison record
        comparison = await findings_service.create_comparison(db, comparison_data, current_user.id)
        
        # Start background comparison
        background_tasks.add_task(
            perform_ai_comparison,
            comparison.id,
            comparison_data.document_ids,
            comparison_data.comparison_type,
            comparison_data.focus_areas
        )
        
        logger.info(f"Comparison {comparison.id} created by user {current_user.id}")
        
        return ComparisonResponse.from_orm(comparison)
        
    except Exception as e:
        logger.error(f"Error creating comparison: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create comparison: {str(e)}"
        )


@comparisons_router.get("/{comparison_id}", response_model=ComparisonDetailResponse)
async def get_comparison(
    comparison_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> ComparisonDetailResponse:
    """Get detailed comparison results"""
    try:
        comparison = await findings_service.get_comparison_by_id(db, comparison_id)
        if not comparison:
            raise ComparisonNotFoundError(f"Comparison {comparison_id} not found")
        
        # Check permissions (assuming company_id is available through documents)
        await require_permissions(current_user, "comparisons:read")
        
        return ComparisonDetailResponse.from_orm(comparison)
        
    except ComparisonNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving comparison {comparison_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve comparison"
        )


@comparisons_router.get("/", response_model=ComparisonListResponse)
async def list_comparisons(
    company_id: Optional[UUID] = Query(None, description="Filter by company ID"),
    comparison_type: Optional[str] = Query(None, description="Filter by comparison type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    created_by: Optional[UUID] = Query(None, description="Filter by creator"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> ComparisonListResponse:
    """List document comparisons with filtering"""
    try:
        filters = {
            "company_id": company_id,
            "comparison_type": comparison_type,
            "status": status,
            "created_by": created_by
        }
        
        comparisons, total_count = await findings_service.list_comparisons(
            db, filters, page, page_size
        )
        
        # Filter by permissions
        accessible_comparisons = []
        for comparison in comparisons:
            try:
                await require_permissions(current_user, "comparisons:read")
                accessible_comparisons.append(ComparisonResponse.from_orm(comparison))
            except:
                continue
        
        return ComparisonListResponse(
            comparisons=accessible_comparisons,
            total_count=len(accessible_comparisons),
            page=page,
            page_size=page_size,
            total_pages=(len(accessible_comparisons) + page_size - 1) // page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing comparisons: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve comparisons"
        )


@comparisons_router.get("/{comparison_id}/discrepancies", response_model=List[DiscrepancyResponse])
async def get_comparison_discrepancies(
    comparison_id: UUID,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    discrepancy_type: Optional[str] = Query(None, description="Filter by type"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> List[DiscrepancyResponse]:
    """Get discrepancies found in a comparison"""
    try:
        # Check comparison exists and permissions
        comparison = await findings_service.get_comparison_by_id(db, comparison_id)
        if not comparison:
            raise ComparisonNotFoundError(f"Comparison {comparison_id} not found")
        
        await require_permissions(current_user, "comparisons:read")
        
        # Get discrepancies
        discrepancies = await findings_service.get_comparison_discrepancies(
            db, comparison_id, severity, discrepancy_type
        )
        
        return [DiscrepancyResponse.from_orm(disc) for disc in discrepancies]
        
    except ComparisonNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving discrepancies for comparison {comparison_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve discrepancies"
        )


@comparisons_router.get("/analytics/risk-assessment", response_model=RiskAssessmentResponse)
async def get_risk_assessment(
    company_id: UUID = Query(..., description="Company ID for risk assessment"),
    time_period: str = Query("90d", description="Time period for assessment"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    risk_service: RiskService = Depends(),
) -> RiskAssessmentResponse:
    """Get comprehensive risk assessment based on findings and comparisons"""
    try:
        await require_permissions(current_user, "analytics:read", resource_id=str(company_id))
        
        # Calculate time range
        time_periods = {"30d": 30, "90d": 90, "180d": 180, "1y": 365}
        days = time_periods.get(time_period, 90)
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get risk assessment
        risk_assessment = await risk_service.calculate_risk_assessment(
            db, company_id, start_date, end_date
        )
        
        return RiskAssessmentResponse(**risk_assessment)
        
    except Exception as e:
        logger.error(f"Error calculating risk assessment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate risk assessment"
        )


@comparisons_router.get("/analytics/trends", response_model=TrendAnalysisResponse)
async def get_trend_analysis(
    company_id: UUID = Query(..., description="Company ID for trend analysis"),
    metric: str = Query("findings_count", description="Metric to analyze trends"),
    time_period: str = Query("1y", description="Time period for trend analysis"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    findings_service: FindingsService = Depends(),
) -> TrendAnalysisResponse:
    """Get trend analysis for findings and compliance metrics"""
    try:
        await require_permissions(current_user, "analytics:read", resource_id=str(company_id))
        
        # Validate metric
        valid_metrics = [
            "findings_count", "severity_distribution", "resolution_time", 
            "compliance_score", "discrepancy_rate"
        ]
        
        if metric not in valid_metrics:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid metric. Valid options: {', '.join(valid_metrics)}"
            )
        
        # Get trend analysis
        trend_analysis = await findings_service.get_trend_analysis(
            db, company_id, metric, time_period
        )
        
        return TrendAnalysisResponse(**trend_analysis)
        
    except Exception as e:
        logger.error(f"Error getting trend analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trend analysis"
        )


@comparisons_router.get("/analytics/compliance-score", response_model=ComplianceScoreResponse)
async def get_compliance_score(
    company_id: UUID = Query(..., description="Company ID for compliance scoring"),
    framework: str = Query("SOX", description="Compliance framework"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    risk_service: RiskService = Depends(),
) -> ComplianceScoreResponse:
    """Get compliance score for specific framework"""
    try:
        await require_permissions(current_user, "analytics:read", resource_id=str(company_id))
        
        if framework not in COMPLIANCE_FRAMEWORKS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid framework. Valid options: {', '.join(COMPLIANCE_FRAMEWORKS)}"
            )
        
        # Calculate compliance score
        compliance_score = await risk_service.calculate_compliance_score(
            db, company_id, framework
        )
        
        return ComplianceScoreResponse(**compliance_score)
        
    except Exception as e:
        logger.error(f"Error calculating compliance score: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate compliance score"
        )


# Background task functions
async def perform_ai_comparison(
    comparison_id: UUID,
    document_ids: List[UUID],
    comparison_type: str,
    focus_areas: List[str]
):
    """Background task for AI-powered document comparison"""
    try:
        ai_service = AIService()
        findings_service = FindingsService()
        
        # Update status to processing
        async with get_db_session() as db:
            await findings_service.update_comparison_status(
                db, comparison_id, "processing", 0
            )
        
        # Perform AI comparison
        comparison_result = await ai_service.compare_documents_advanced(
            document_ids=document_ids,
            comparison_type=comparison_type,
            focus_areas=focus_areas
        )
        
        # Store results
        async with get_db_session() as db:
            await findings_service.store_comparison_results(
                db, comparison_id, comparison_result
            )
            
            await findings_service.update_comparison_status(
                db, comparison_id, "completed", 100
            )
        
        logger.info(f"AI comparison {comparison_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error in AI comparison {comparison_id}: {str(e)}")
        
        # Update status to failed
        async with get_db_session() as db:
            await findings_service.update_comparison_status(
                db, comparison_id, "failed", 0, str(e)
            )


# Combine routers
router = APIRouter()
router.include_router(findings_router)
router.include_router(comparisons_router)