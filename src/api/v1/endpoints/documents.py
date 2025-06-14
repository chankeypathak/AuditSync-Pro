"""
Documents API endpoints for AuditSync-Pro
Handles document upload, processing, and retrieval operations
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from src.core.database import get_db_session
from src.core.auth import get_current_user, require_permissions
from src.core.config import get_settings
from src.models.documents import Document, DocumentFinding, DocumentProcessingStatus
from src.models.users import User
from src.schemas.documents import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListResponse,
    DocumentFindingResponse,
    DocumentProcessingResponse,
    DocumentUploadResponse,
    DocumentSearchRequest,
    DocumentComparisonRequest,
    DocumentComparisonResponse
)
from src.services.document_service import DocumentService
from src.services.ai_service import AIService
from src.services.storage_service import StorageService
from src.utils.exceptions import DocumentNotFoundError, DocumentProcessingError
from src.utils.validators import validate_document_type, validate_file_size
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/documents", tags=["documents"])

# Document type mappings
DOCUMENT_TYPE_MAPPING = {
    "internal": ["audit_report", "management_letter", "risk_assessment", "control_assessment"],
    "sec": ["10-K", "10-Q", "8-K", "DEF-14A", "proxy_statement"],
    "vendor": ["soc_report", "penetration_test", "compliance_assessment", "external_audit"]
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".csv", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_id: UUID = Query(..., description="Company ID for document association"),
    document_type: str = Query(..., description="Type of document (10-K, audit_report, etc.)"),
    source_type: str = Query(..., description="Source type (internal, sec, vendor)"),
    report_period: Optional[str] = Query(None, description="Report period (YYYY-MM-DD)"),
    description: Optional[str] = Query(None, description="Document description"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
    storage_service: StorageService = Depends(),
) -> DocumentUploadResponse:
    """
    Upload a new audit document for processing
    
    Supports multiple file formats and automatically triggers AI processing pipeline
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is required"
            )
        
        # Check file extension
        file_extension = "." + file.filename.split(".")[-1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file_extension} not supported. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Validate file size
        file_content = await file.read()
        await file.seek(0)  # Reset file pointer
        
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )
        
        # Validate document type and source
        validate_document_type(document_type, source_type)
        
        # Generate unique document ID
        document_id = uuid4()
        
        # Create document record
        document_data = DocumentCreate(
            id=document_id,
            company_id=company_id,
            filename=file.filename,
            document_type=document_type,
            source_type=source_type,
            file_size=len(file_content),
            content_type=file.content_type,
            report_period=datetime.fromisoformat(report_period) if report_period else None,
            description=description,
            uploaded_by=current_user.id,
            processing_status=DocumentProcessingStatus.PENDING
        )
        
        # Save document to database
        document = await document_service.create_document(db, document_data)
        
        # Upload file to storage
        file_path = await storage_service.upload_file(
            file_content,
            f"documents/{company_id}/{document_id}/{file.filename}"
        )
        
        # Update document with file path
        document.file_path = file_path
        await db.commit()
        
        # Schedule background processing
        background_tasks.add_task(
            process_document_background,
            document_id,
            file_path,
            file_content
        )
        
        logger.info(f"Document {document_id} uploaded successfully by user {current_user.id}")
        
        return DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="uploaded",
            processing_status="pending",
            message="Document uploaded successfully. Processing will begin shortly."
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
) -> DocumentResponse:
    """Get document details by ID"""
    try:
        document = await document_service.get_document_by_id(db, document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        
        # Check permissions
        await require_permissions(current_user, "documents:read", resource_id=str(document.company_id))
        
        return DocumentResponse.from_orm(document)
        
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    company_id: Optional[UUID] = Query(None, description="Filter by company ID"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    processing_status: Optional[str] = Query(None, description="Filter by processing status"),
    report_period_start: Optional[str] = Query(None, description="Filter by report period start date"),
    report_period_end: Optional[str] = Query(None, description="Filter by report period end date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
) -> DocumentListResponse:
    """List documents with filtering and pagination"""
    try:
        # Build filters
        filters = {}
        if company_id:
            filters['company_id'] = company_id
        if source_type:
            filters['source_type'] = source_type
        if document_type:
            filters['document_type'] = document_type
        if processing_status:
            filters['processing_status'] = processing_status
        if report_period_start:
            filters['report_period_start'] = datetime.fromisoformat(report_period_start)
        if report_period_end:
            filters['report_period_end'] = datetime.fromisoformat(report_period_end)
        
        # Get paginated results
        documents, total_count = await document_service.list_documents(
            db, filters, page, page_size
        )
        
        # Check permissions for each document
        accessible_documents = []
        for doc in documents:
            try:
                await require_permissions(current_user, "documents:read", resource_id=str(doc.company_id))
                accessible_documents.append(DocumentResponse.from_orm(doc))
            except:
                continue  # Skip documents user doesn't have access to
        
        return DocumentListResponse(
            documents=accessible_documents,
            total_count=len(accessible_documents),
            page=page,
            page_size=page_size,
            total_pages=(len(accessible_documents) + page_size - 1) // page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.post("/search", response_model=DocumentListResponse)
async def search_documents(
    search_request: DocumentSearchRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
    ai_service: AIService = Depends(),
) -> DocumentListResponse:
    """
    Semantic search across document content using AI embeddings
    """
    try:
        # Perform semantic search
        search_results = await ai_service.semantic_search(
            query=search_request.query,
            filters={
                "company_ids": search_request.company_ids,
                "source_types": search_request.source_types,
                "document_types": search_request.document_types,
                "date_range": {
                    "start": search_request.date_range_start,
                    "end": search_request.date_range_end
                }
            },
            limit=search_request.limit or 20
        )
        
        # Convert to document responses
        documents = []
        for result in search_results:
            try:
                await require_permissions(current_user, "documents:read", resource_id=str(result.company_id))
                documents.append(DocumentResponse.from_orm(result))
            except:
                continue
        
        return DocumentListResponse(
            documents=documents,
            total_count=len(documents),
            page=1,
            page_size=len(documents),
            total_pages=1
        )
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search documents"
        )


@router.get("/{document_id}/findings", response_model=List[DocumentFindingResponse])
async def get_document_findings(
    document_id: UUID,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
) -> List[DocumentFindingResponse]:
    """Get AI-extracted findings from a document"""
    try:
        # Check document exists and permissions
        document = await document_service.get_document_by_id(db, document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        
        await require_permissions(current_user, "documents:read", resource_id=str(document.company_id))
        
        # Get findings
        findings = await document_service.get_document_findings(
            db, document_id, severity, category
        )
        
        return [DocumentFindingResponse.from_orm(finding) for finding in findings]
        
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving findings for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document findings"
        )


@router.post("/compare", response_model=DocumentComparisonResponse)
async def compare_documents(
    comparison_request: DocumentComparisonRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
    ai_service: AIService = Depends(),
) -> DocumentComparisonResponse:
    """
    Compare multiple documents to identify discrepancies and inconsistencies
    """
    try:
        # Validate documents exist and user has access
        documents = []
        for doc_id in comparison_request.document_ids:
            doc = await document_service.get_document_by_id(db, doc_id)
            if not doc:
                raise DocumentNotFoundError(f"Document {doc_id} not found")
            
            await require_permissions(current_user, "documents:read", resource_id=str(doc.company_id))
            documents.append(doc)
        
        # Check if documents are processed
        unprocessed_docs = [doc for doc in documents if doc.processing_status != DocumentProcessingStatus.COMPLETED]
        if unprocessed_docs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Documents must be fully processed before comparison. Unprocessed: {[str(doc.id) for doc in unprocessed_docs]}"
            )
        
        # Generate comparison ID
        comparison_id = uuid4()
        
        # Start comparison in background
        background_tasks.add_task(
            perform_document_comparison,
            comparison_id,
            comparison_request.document_ids,
            comparison_request.comparison_type,
            comparison_request.focus_areas,
            current_user.id
        )
        
        logger.info(f"Document comparison {comparison_id} initiated by user {current_user.id}")
        
        return DocumentComparisonResponse(
            comparison_id=comparison_id,
            status="initiated",
            message="Document comparison has been initiated. Results will be available shortly.",
            document_count=len(comparison_request.document_ids),
            estimated_completion_time=datetime.utcnow().isoformat()
        )
        
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error initiating document comparison: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate document comparison"
        )


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
    storage_service: StorageService = Depends(),
):
    """Download original document file"""
    try:
        # Check document exists and permissions
        document = await document_service.get_document_by_id(db, document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        
        await require_permissions(current_user, "documents:download", resource_id=str(document.company_id))
        
        # Get file from storage
        file_content = await storage_service.get_file(document.file_path)
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=document.content_type or "application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={document.filename}"}
        )
        
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document"
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
    storage_service: StorageService = Depends(),
):
    """Delete a document and all associated data"""
    try:
        # Check document exists and permissions
        document = await document_service.get_document_by_id(db, document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        
        await require_permissions(current_user, "documents:delete", resource_id=str(document.company_id))
        
        # Delete from storage
        if document.file_path:
            await storage_service.delete_file(document.file_path)
        
        # Delete from database (cascade will handle related records)
        await document_service.delete_document(db, document_id)
        
        logger.info(f"Document {document_id} deleted by user {current_user.id}")
        
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.get("/{document_id}/processing-status", response_model=DocumentProcessingResponse)
async def get_processing_status(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(),
) -> DocumentProcessingResponse:
    """Get current processing status of a document"""
    try:
        document = await document_service.get_document_by_id(db, document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        
        await require_permissions(current_user, "documents:read", resource_id=str(document.company_id))
        
        return DocumentProcessingResponse(
            document_id=document_id,
            status=document.processing_status,
            progress_percentage=document.processing_progress or 0,
            current_stage=document.processing_stage,
            error_message=document.processing_error,
            started_at=document.processing_started_at,
            completed_at=document.processing_completed_at,
            estimated_completion=document.estimated_completion_time
        )
        
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    except Exception as e:
        logger.error(f"Error getting processing status for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get processing status"
        )


# Background task functions
async def process_document_background(
    document_id: UUID,
    file_path: str,
    file_content: bytes
):
    """Background task for document processing"""
    try:
        # Initialize services
        document_service = DocumentService()
        ai_service = AIService()
        
        # Update status to processing
        async with get_db_session() as db:
            await document_service.update_processing_status(
                db, document_id, DocumentProcessingStatus.PROCESSING, 0, "Starting document processing"
            )
        
        # Process document through AI pipeline
        processing_result = await ai_service.process_document(
            document_id=document_id,
            file_content=file_content,
            file_path=file_path
        )
        
        # Update with results
        async with get_db_session() as db:
            await document_service.update_processing_status(
                db, document_id, DocumentProcessingStatus.COMPLETED, 100, "Processing completed"
            )
            
            # Store findings
            if processing_result.findings:
                await document_service.store_document_findings(
                    db, document_id, processing_result.findings
                )
        
        logger.info(f"Document {document_id} processed successfully")
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        
        # Update status to failed
        async with get_db_session() as db:
            await document_service.update_processing_status(
                db, document_id, DocumentProcessingStatus.FAILED, 0, f"Processing failed: {str(e)}"
            )


async def perform_document_comparison(
    comparison_id: UUID,
    document_ids: List[UUID],
    comparison_type: str,
    focus_areas: List[str],
    user_id: UUID
):
    """Background task for document comparison"""
    try:
        # Initialize services
        ai_service = AIService()
        
        # Perform comparison
        comparison_result = await ai_service.compare_documents(
            comparison_id=comparison_id,
            document_ids=document_ids,
            comparison_type=comparison_type,
            focus_areas=focus_areas
        )
        
        # Store results (implementation depends on comparison results schema)
        # This would typically store in a comparisons table
        
        logger.info(f"Document comparison {comparison_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error performing document comparison {comparison_id}: {str(e)}")
