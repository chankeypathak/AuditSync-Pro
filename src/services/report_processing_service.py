from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from src.models import AuditReport, Company
from src.services.document_processor import document_processor
from src.services.ai_service import ai_service
from src.services.llm_service import llm_service
from src.core.database import get_db

logger = logging.getLogger(__name__)

class ReportProcessingService:
    """Service for processing audit reports through the complete pipeline"""
    
    def __init__(self):
        self.document_processor = document_processor
        self.ai_service = ai_service
        self.llm_service = llm_service
    
    async def process_uploaded_report(
        self,
        db: Session,
        file_path: str,
        filename: str,
        company_id: UUID,
        report_type: str,
        source: str,
        report_date: datetime,
        fiscal_year: int,
        fiscal_quarter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process newly uploaded audit report through complete pipeline"""
        try:
            # Step 1: Process document and extract text
            processing_result = self.document_processor.process_document(file_path, filename)
            
            if not processing_result['valid']:
                return {
                    'success': False,
                    'error': processing_result['error']
                }
            
            # Step 2: Create audit report record
            audit_report = AuditReport(
                company_id=company_id,
                report_type=report_type,
                source=source,
                file_path=file_path,
                file_name=filename,
                file_size=processing_result['file_size'],
                file_hash=processing_result['file_hash'],
                report_date=report_date,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                raw_text=processing_result['raw_text'],
                status='processing'
            )
            
            db.add(audit_report)
            db.commit()
            db.refresh(audit_report)
            
            # Step 3: Generate embeddings
            embeddings = await self.ai_service.generate_embeddings(processing_result['raw_text'])
            audit_report.embeddings = embeddings
            
            # Step 4: Extract key findings using LLM
            findings_result = await self.ai_service.extract_key_findings(processing_result['raw_text'])
            audit_report.key_findings = findings_result
            
            # Step 5: Detect material weaknesses
            material_weaknesses = await self.llm_service.detect_material_weaknesses(processing_result['raw_text'])
            
            # Step 6: Categorize risks
            risk_categories = await self.llm_service.categorize_risks(processing_result['raw_text'])
            audit_report.risk_categories = risk_categories.get('risk_categories', {}).get('categories', [])
            
            # Step 7: Assess compliance scores
            compliance_assessment = await self._assess_compliance_scores(processing_result['raw_text'])
            audit_report.compliance_scores = compliance_assessment
            
            # Step 8: Create structured data
            structured_data = {
                'metadata': processing_result['metadata'],
                'material_weaknesses': material_weaknesses,
                'risk_assessment': risk_categories,
                'compliance_scores': compliance_assessment,
                'processing_summary': {
                    'total_words': len(processing_result['raw_text'].split()),
                    'total_characters': len(processing_result['raw_text']),
                    'embedding_dimensions': len(embeddings) if embeddings else 0,
                    'findings_extracted': len(findings_result) if isinstance(findings_result, dict) else 0
                }
            }
            
            audit_report.structured_data = structured_data
            audit_report.status = 'processed'
            audit_report.processed_at = datetime.utcnow()
            
            db.commit()
            
            return {
                'success': True,
                'report_id': audit_report.id,
                'processing_summary': structured_data['processing_summary'],
                'status': 'processed'
            }
            
        except Exception as e:
            logger.error(f'Report processing error: {str(e)}')
            
            # Update report status to error if it was created
            if 'audit_report' in locals():
                audit_report.status = 'error'
                db.commit()
            
            return {
                'success': False,
                'error': f'Failed to process report: {str(e)}'
            }
    
    async def _assess_compliance_scores(self, text: str) -> Dict[str, Any]:
        """Assess compliance scores for different frameworks"""
        try:
            # Define compliance frameworks to assess
            frameworks = {
                'SOX': 'Sarbanes-Oxley compliance',
                'COSO': 'COSO framework adherence',
                'PCAOB': 'PCAOB standards compliance',
                'SEC': 'SEC reporting requirements'
            }
            
            compliance_scores = {}
            
            for framework, description in frameworks.items():
                # Simple keyword-based scoring (would be more sophisticated in production)
                score = self._calculate_framework_score(text, framework)
                compliance_scores[framework] = {
                    'score': score,
                    'description': description,
                    'assessment_date': datetime.utcnow().isoformat()
                }
            
            return compliance_scores
            
        except Exception as e:
            logger.error(f'Compliance assessment error: {str(e)}')
            return {}
    
    def _calculate_framework_score(self, text: str, framework: str) -> float:
        """Calculate compliance score for specific framework"""
        try:
            text_lower = text.lower()
            
            # Define keywords for each framework
            framework_keywords = {
                'SOX': ['internal control', 'material weakness', 'significant deficiency', 'financial reporting'],
                'COSO': ['control environment', 'risk assessment', 'control activities', 'monitoring'],
                'PCAOB': ['audit standard', 'audit opinion', 'audit evidence', 'audit risk'],
                'SEC': ['disclosure', 'financial statement', 'filing', 'regulation']
            }
            
            keywords = framework_keywords.get(framework, [])
            
            # Count keyword occurrences
            keyword_count = sum(text_lower.count(keyword) for keyword in keywords)
            
            # Calculate score based on keyword frequency (0-100 scale)
            word_count = len(text.split())
            frequency = keyword_count / word_count if word_count > 0 else 0
            
            # Convert to 0-100 scale
            score = min(frequency * 1000, 100)  # Scale factor of 1000
            
            return round(score, 2)
            
        except Exception as e:
            logger.error(f'Framework score calculation error: {str(e)}')
            return 0.0
    
    async def reprocess_report(self, db: Session, report_id: UUID) -> Dict[str, Any]:
        """Reprocess an existing report with updated AI models"""
        try:
            # Get report
            report = db.query(AuditReport).filter(AuditReport.id == report_id).first()
            if not report:
                return {'success': False, 'error': 'Report not found'}
            
            if not report.raw_text:
                return {'success': False, 'error': 'Report has no raw text to process'}
            
            # Update status
            report.status = 'processing'
            db.commit()
            
            # Regenerate embeddings
            embeddings = await self.ai_service.generate_embeddings(report.raw_text)
            report.embeddings = embeddings
            
            # Re-extract findings
            findings_result = await self.ai_service.extract_key_findings(report.raw_text)
            report.key_findings = findings_result
            
            # Re-detect material weaknesses
            material_weaknesses = await self.llm_service.detect_material_weaknesses(report.raw_text)
            
            # Re-categorize risks
            risk_categories = await self.llm_service.categorize_risks(report.raw_text)
            report.risk_categories = risk_categories.get('risk_categories', {}).get('categories', [])
            
            # Update structured data
            report.structured_data.update({
                'reprocessed_at': datetime.utcnow().isoformat(),
                'material_weaknesses': material_weaknesses,
                'risk_assessment': risk_categories
            })
            
            report.status = 'processed'
            report.processed_at = datetime.utcnow()
            
            db.commit()
            
            return {
                'success': True,
                'report_id': report_id,
                'status': 'reprocessed'
            }
            
        except Exception as e:
            logger.error(f'Report reprocessing error: {str(e)}')
            return {'success': False, 'error': f'Failed to reprocess report: {str(e)}'}
    
    def get_processing_stats(self, db: Session, company_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get processing statistics"""
        try:
            query = db.query(AuditReport)
            
            if company_id:
                query = query.filter(AuditReport.company_id == company_id)
            
            reports = query.all()
            
            total_reports = len(reports)
            processed_reports = len([r for r in reports if r.status == 'processed'])
            processing_reports = len([r for r in reports if r.status == 'processing'])
            error_reports = len([r for r in reports if r.status == 'error'])
            
            return {
                'total_reports': total_reports,
                'processed_reports': processed_reports,
                'processing_reports': processing_reports,
                'error_reports': error_reports,
                'success_rate': round(processed_reports / total_reports * 100, 2) if total_reports > 0 else 0
            }
            
        except Exception as e:
            logger.error(f'Processing stats error: {str(e)}')
            return {'error': str(e)}

# Initialize report processing service
report_processing_service = ReportProcessingService()
