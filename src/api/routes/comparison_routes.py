from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
import asyncio

from src.services.comparison_service import ComparisonService
from src.models.schemas import ComparisonRequest, ComparisonResponse, ComparisonSummary
from src.core.dependencies import get_comparison_service

router = APIRouter()

@router.post("/compare", response_model=ComparisonResponse)
async def compare_reports(
    request: ComparisonRequest,
    background_tasks: BackgroundTasks,
    comparison_service: ComparisonService = Depends(get_comparison_service)
):
    """Compare multiple audit reports"""
    try:
        # Start comparison in background
        task_id = await comparison_service.start_comparison(request)
        background_tasks.add_task(comparison_service.process_comparison, task_id)
        
        return ComparisonResponse(
            task_id=task_id,
            status="started",
            message="Comparison started successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compare/{task_id}", response_model=ComparisonResponse)
async def get_comparison_status(
    task_id: str,
    comparison_service: ComparisonService = Depends(get_comparison_service)
):
    """Get comparison task status and results"""
    result = await comparison_service.get_comparison_status(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Comparison task not found")
    return result

@router.get("/summaries", response_model=List[ComparisonSummary])
async def get_comparison_summaries(
    company_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    comparison_service: ComparisonService = Depends(get_comparison_service)
):
    """Get comparison summaries"""
    return await comparison_service.get_summaries(company_id, limit, offset)

@router.post("/analyze-discrepancies")
async def analyze_discrepancies(
    comparison_id: str,
    comparison_service: ComparisonService = Depends(get_comparison_service)
):
    """Deep analysis of identified discrepancies"""
    try:
        analysis = await comparison_service.analyze_discrepancies(comparison_id)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
