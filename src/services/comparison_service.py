from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from src.models import AuditReport, Comparison, Company
from src.services.ai_service import ai_service
from src.core.database import get_db

logger = logging.getLogger(__name__)

class ComparisonService:
    """Service for managing audit report comparisons"""
    
    def __init__(self):
        self.ai_service = ai_service
    
    async def create_comparison(
        self,
        db: Session,
        company_id: UUID,
        source_report_id: UUID,
        target_report_id: UUID,
        comparison_type: str
    ) -> Comparison:
        """Create a new comparison between two reports"""
        try:
            # Validate reports exist
            source_report = db.query(AuditReport).filter(AuditReport.id == source_report_id).first()
            target_report = db.query(AuditReport).filter(AuditReport.id == target_report_id).first()
            
            if not source_report or not target_report:
                raise ValueError('One or both reports not found')
            
            # Create comparison record
            comparison = Comparison(
                company_id=company_id,
                source_report_id=source_report_id,
                target_report_id=target_report_id,
                comparison_type=comparison_type,
                status='pending'
            )
            
            db.add(comparison)
            db.commit()
            db.refresh(comparison)
            
            return comparison
            
        except Exception as e:
            logger.error(f'Comparison creation error: {str(e)}')
            db.rollback()
            raise ValueError(f'Failed to create comparison: {str(e)}')
    
    async def process_comparison(self, db: Session, comparison_id: UUID) -> Dict[str, Any]:
        """Process a comparison using AI services"""
        try:
            # Get comparison record
            comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
            if not comparison:
                raise ValueError('Comparison not found')
            
            # Update status to processing
            comparison.status = 'processing'
            db.commit()
            
            # Get source and target reports
            source_report = db.query(AuditReport).filter(AuditReport.id == comparison.source_report_id).first()
            target_report = db.query(AuditReport).filter(AuditReport.id == comparison.target_report_id).first()
            
            if not source_report.raw_text or not target_report.raw_text:
                raise ValueError('Reports must be processed before comparison')
            
            # Perform AI-powered comparison
            comparison_result = await self.ai_service.compare_reports(
                source_report.raw_text,
                target_report.raw_text
            )
            
            # Calculate embedding similarity if embeddings exist
            similarity_score = 0.0
            if source_report.embeddings and target_report.embeddings:
                similarity_score = self.ai_service.calculate_similarity(
                    source_report.embeddings,
                    target_report.embeddings
                )
            
            # Update comparison with results
            comparison.similarity_score = similarity_score
            comparison.key_differences = comparison_result.get('key_differences', {})
            comparison.risk_alignment = comparison_result.get('risk_alignment', {})
            comparison.compliance_gaps = comparison_result.get('compliance_gaps', {})
            comparison.recommendations = comparison_result.get('recommendations', {})
            comparison.status = 'completed'
            comparison.completed_at = datetime.utcnow()
            
            # Perform detailed section analysis
            section_analysis = await self._analyze_sections(source_report.raw_text, target_report.raw_text)
            comparison.section_comparisons = section_analysis
            
            # Assess materiality
            materiality_assessment = await self._assess_materiality(comparison_result)
            comparison.materiality_assessment = materiality_assessment
            
            db.commit()
            
            return {
                'comparison_id': comparison_id,
                'status': 'completed',
                'similarity_score': similarity_score,
                'results': comparison_result
            }
            
        except Exception as e:
            logger.error(f'Comparison processing error: {str(e)}')
            
            # Update comparison status to error
            comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
            if comparison:
                comparison.status = 'error'
                db.commit()
            
            raise ValueError(f'Failed to process comparison: {str(e)}')
    
    async def _analyze_sections(self, source_text: str, target_text: str) -> Dict[str, Any]:
        """Perform detailed section-by-section analysis"""
        try:
            # Define common audit report sections
            sections = [
                'Executive Summary',
                'Scope and Methodology',
                'Key Findings',
                'Material Weaknesses',
                'Significant Deficiencies',
                'Risk Assessment',
                'Recommendations',
                'Management Response'
            ]
            
            section_analysis = {}
            
            for section in sections:
                # Extract section content (simplified - in reality would use more sophisticated parsing)
                source_section = self._extract_section(source_text, section)
                target_section = self._extract_section(target_text, section)
                
                if source_section and target_section:
                    # Compare sections
                    comparison = await self.ai_service.compare_reports(source_section, target_section)
                    section_analysis[section] = comparison
            
            return section_analysis
            
        except Exception as e:
            logger.error(f'Section analysis error: {str(e)}')
            return {}
    
    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """Extract specific section from audit report text"""
        try:
            # Simplified section extraction - would be more sophisticated in production
            lines = text.split('\n')
            in_section = False
            section_content = []
            
            for line in lines:
                if section_name.lower() in line.lower():
                    in_section = True
                    continue
                
                if in_section:
                    # Stop if we hit another section header
                    if any(header in line.lower() for header in ['summary', 'scope', 'findings', 'recommendations']):
                        if line.strip() and not line.startswith(' '):  # New section header
                            break
                    
                    section_content.append(line)
                    
                    # Stop if we've collected enough content
                    if len(section_content) > 50:  # Limit section size
                        break
            
            return '\n'.join(section_content).strip() if section_content else None
            
        except Exception as e:
            logger.error(f'Section extraction error: {str(e)}')
            return None
    
    async def _assess_materiality(self, comparison_result: Dict[str, Any]) -> Dict[str, Any]:
        """Assess materiality of differences found in comparison"""
        try:
            # Simple materiality assessment based on comparison results
            materiality_score = 0
            
            # Check for material weaknesses
            if 'material_weaknesses' in str(comparison_result).lower():
                materiality_score += 3
            
            # Check for significant deficiencies
            if 'significant_deficiencies' in str(comparison_result).lower():
                materiality_score += 2
            
            # Check for compliance issues
            if 'compliance' in str(comparison_result).lower():
                materiality_score += 2
            
            # Determine materiality level
            if materiality_score >= 5:
                level = 'High'
            elif materiality_score >= 3:
                level = 'Medium'
            else:
                level = 'Low'
            
            return {
                'materiality_level': level,
                'materiality_score': materiality_score,
                'assessment_date': datetime.utcnow().isoformat(),
                'factors_considered': [
                    'Material weaknesses',
                    'Significant deficiencies',
                    'Compliance issues'
                ]
            }
            
        except Exception as e:
            logger.error(f'Materiality assessment error: {str(e)}')
            return {'materiality_level': 'Unknown', 'error': str(e)}
    
    def get_comparison_history(self, db: Session, company_id: UUID) -> List[Comparison]:
        """Get comparison history for a company"""
        return db.query(Comparison).filter(
            Comparison.company_id == company_id
        ).order_by(Comparison.created_at.desc()).all()
    
    def get_comparison_stats(self, db: Session, company_id: UUID) -> Dict[str, Any]:
        """Get comparison statistics for a company"""
        comparisons = self.get_comparison_history(db, company_id)
        
        total_comparisons = len(comparisons)
        completed_comparisons = len([c for c in comparisons if c.status == 'completed'])
        avg_similarity = 0.0
        
        if completed_comparisons > 0:
            similarities = [c.similarity_score for c in comparisons if c.similarity_score is not None]
            if similarities:
                avg_similarity = sum(similarities) / len(similarities)
        
        return {
            'total_comparisons': total_comparisons,
            'completed_comparisons': completed_comparisons,
            'pending_comparisons': total_comparisons - completed_comparisons,
            'average_similarity': round(avg_similarity, 3),
            'last_comparison': comparisons[0].created_at if comparisons else None
        }

# Initialize comparison service
comparison_service = ComparisonService()
