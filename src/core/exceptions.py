from fastapi import HTTPException
from typing import Optional, Dict, Any
import traceback
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class AuditGenAIException(Exception):
    """Base exception for the application"""
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class LLMServiceException(AuditGenAIException):
    """Exception for LLM service errors"""
    pass

class VectorServiceException(AuditGenAIException):
    """Exception for vector database errors"""
    pass

class ComparisonException(AuditGenAIException):
    """Exception for comparison engine errors"""
    pass

class DataIngestionException(AuditGenAIException):
    """Exception for data ingestion errors"""
    pass

async def handle_exception(exc: Exception) -> HTTPException:
    """Global exception handler"""
    logger.error("Unhandled exception occurred", 
                exception=str(exc), 
                traceback=traceback.format_exc())
    
    if isinstance(exc, AuditGenAIException):
        return HTTPException(
            status_code=400,
            detail={
                "message": exc.message,
                "error_code": exc.error_code,
                "details": exc.details
            }
        )
    
    return HTTPException(
        status_code=500,
        detail={"message": "Internal server error", "error_code": "INTERNAL_ERROR"}
    )
