from typing import Optional, List, Dict, Any
import asyncio
import hashlib
from pathlib import Path
import aiofiles
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.models.database_models import AuditReport, Company
from src.models.schemas import AuditReportCreate, AuditReportResponse
from src.services.llm_service import LLMService
from src.services.vector_service import VectorService
from src.core.config import settings
from src.core.logging_config import get_logger
from src.core.exceptions import DataIngestionException
from src.utils.document_processor import DocumentProcessor

logger = get_logger(__name__)

class AuditService:
    def __init__(self, db: AsyncSession, llm_service: LLMService, vector_service: VectorService):
        self.db = db
        self.llm_service = llm_service
        self.vector_service = vector_service
        self.document_processor = DocumentProcessor()
    
    async def process_upload(self, file: UploadFile, report_type: str, company_id: str) -> AuditReportResponse:
        """Process uploaded audit report file"""
        try:
            # Validate file
            if not self._validate_file(file):
                raise DataIngestionException("Invalid file format or size")
            
            # Generate file hash
            content = await file.read()
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Check for duplicate
            existing = await self._check_duplicate(content_hash)
            if existing:
                logger.info(f"Duplicate file detected: {file.filename}")
                return AuditReportResponse.from_orm(existing)
            
            # Save file
            file_path = await self._save_file(file, content)
            
            # Create database record
            audit_report = AuditReport(
                company_id=company_id,
                title=self._extract_title(file.filename),
                report_type=report_type,
                file_path=str(file_path),
                file_name=file.filename,
                file_size=len(content),
                content_hash=content_hash,
                extraction_status="pending"
            )
            
            self.db.add(audit_report)
            await self.db.commit()
            await self.db.refresh(audit_report)
            
            # Process document asynchronously
            asyncio.create_task(self._process_document(audit_report.id))
            
            return AuditReportResponse.from_orm(audit_report)
            
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}")
            await self.db.rollback()
            raise DataIngestionException(f"Failed to process upload: {str(e)}")
    
    async def get_reports(self, company_id: Optional[str] = None, report_type: Optional[str] = None, 
                         limit: int = 50, offset: int = 0) -> List[AuditReportResponse]:
        """Get list of audit reports"""
        query = select(AuditReport)
        
        if company_id:
            query = query.where(AuditReport.company_id == company_id)
        if report_type:
            query = query.where(AuditReport.report_type == report_type)
            
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        reports = result.scalars().all()
        
        return [AuditReportResponse.from_orm(report) for report in reports]
    
    async def get_report_by_id(self, report_id: str) -> Optional[AuditReportResponse]:
        """Get specific audit report"""
        query = select(AuditReport).where(AuditReport.id == report_id)
        result = await self.db.execute(query)
        report = result.scalar_one_or_none()
        
        return AuditReportResponse.from_orm(report) if report else None
    
    def _validate_file(self, file: UploadFile) -> bool:
        """Validate uploaded file"""
        allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
        max_size = 50 * 1024 * 1024  # 50MB
        
        return (file.content_type in allowed_types and 
                hasattr(file, 'size') and file.size <= max_size)
    
    async def _check_duplicate(self, content_hash: str) -> Optional[AuditReport]:
        """Check for duplicate file"""
        query = select(AuditReport).where(AuditReport.content_hash == content_hash)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _save_file(self, file: UploadFile, content: bytes) -> Path:
        """Save uploaded file to disk"""
        upload_dir = settings.UPLOAD_PATH
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / file.filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        return file_path
    
    def _extract_title(self, filename: str) -> str:
        """Extract title from filename"""
        return Path(filename).stem.replace('_', ' ').replace('-', ' ').title()
    
    async def _process_document(self, report_id: str):
        """Process document content extraction and embedding"""
        try:
            # Update status
            await self._update_status(report_id, "processing")
            
            # Get report
            query = select(AuditReport).where(AuditReport.id == report_id)
            result = await self.db.execute(query)
            report = result.scalar_one()
            
            if not report:
                return
            
            # Extract text
            raw_text = await self.document_processor.extract_text(report.file_path)
            processed_text = await self.document_processor.clean_text(raw_text)
            
            # Generate embeddings
            embedding_id = await self.vector_service.store_document(
                document_id=str(report.id),
                text=processed_text,
                metadata={
                    'report_type': report.report_type,
                    'company_id': str(report.company_id),
                    'title': report.title
                }
            )
            
            # Update report
            report.raw_text = raw_text
            report.processed_text = processed_text
            report.vector_embedding_id = embedding_id
            report.extraction_status = "completed"
            
            await self.db.commit()
            
            logger.info(f"Document processing completed for report {report_id}")
            
        except Exception as e:
            logger.error(f"Error processing document {report_id}: {str(e)}")
            await self._update_status(report_id, "failed")
    
    async def _update_status(self, report_id: str, status: str):
        """Update report processing status"""
        query = select(AuditReport).where(AuditReport.id == report_id)
        result = await self.db.execute(query)
        report = result.scalar_one_or_none()
        
        if report:
            report.extraction_status = status
            await self.db.commit()

