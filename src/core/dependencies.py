from functools import lru_cache
from src.services.audit_service import AuditService
from src.services.comparison_service import ComparisonService
from src.services.dashboard_service import DashboardService
from src.services.llm_service import LLMService
from src.services.vector_service import VectorService
from src.core.database import get_db

@lru_cache()
def get_llm_service() -> LLMService:
    """Get LLM service instance"""
    return LLMService()

@lru_cache()
def get_vector_service() -> VectorService:
    """Get Vector service instance"""
    return VectorService()

async def get_audit_service(db=None) -> AuditService:
    """Get Audit service instance"""
    if db is None:
        db = await get_db().__anext__()
    return AuditService(db, get_llm_service(), get_vector_service())

async def get_comparison_service(db=None) -> ComparisonService:
    """Get Comparison service instance"""
    if db is None:
        db = await get_db().__anext__()
    return ComparisonService(db, get_llm_service(), get_vector_service())

async def get_dashboard_service(db=None) -> DashboardService:
    """Get Dashboard service instance"""
    if db is None:
        db = await get_db().__anext__()
    return DashboardService(db)
