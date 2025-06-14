import openai
import asyncio
from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime
from src.core.config import settings
from src.services.ai_service import ai_service

logger = logging.getLogger(__name__)

class LLMService:
    """Service for managing LLM operations and workflows"""
    
    def __init__(self):
        # Initialize OpenAI client
        openai.api_key = settings.OPENAI_API_KEY
        self.ai_service = ai_service
        
        # LLM model configurations
        self.models = {
            'gpt-4': {
                'max_tokens': 8192,
                'temperature': 0.1,
                'suitable_for': ['complex_analysis', 'detailed_comparison', 'risk_assessment']
            },
            'gpt-3.5-turbo': {
                'max_tokens': 4096,
                'temperature': 0.1,
                'suitable_for': ['simple_extraction', 'classification', 'summarization']
            }
        }
        
        # Specialized prompts for different audit tasks
        self.audit_prompts = {
            'material_weakness_detection': """
            Analyze the following audit report text and identify any material weaknesses:
            
            Text: {text}
            
            Please identify and categorize:
            1. Internal control deficiencies
            2. Financial reporting issues
            3. Compliance violations
            4. Risk management failures
            
            For each material weakness found, provide:
            - Description
            - Severity level (High/Medium/Low)
            - Potential impact
            - Remediation recommendations
            
            Return response in JSON format.
            """,
            
            'compliance_gap_analysis': """
            Compare the following two audit reports and identify compliance gaps:
            
            Internal Audit Report: {internal_report}
            
            External/SEC Report: {external_report}
            
            Please analyze:
            1. Regulatory compliance differences
            2. Control environment gaps
            3. Risk assessment discrepancies
            4. Reporting standard variations
            
            Return detailed gap analysis in JSON format.
            """,
            
            'risk_categorization': """
            Categorize the risks mentioned in this audit report:
            
            Text: {text}
            
            Please categorize risks into:
            1. Strategic risks
            2. Operational risks
            3. Financial risks
            4. Compliance risks
            5. Reputational risks
            
            For each risk category, provide:
            - Risk items identified
            - Likelihood assessment
            - Impact assessment
            - Mitigation strategies mentioned
            
            Return response in JSON format.
            """,
            
            'executive_summary_generation': """
            Generate an executive summary for the following audit comparison:
            
            Comparison Results: {comparison_data}
            
            Key Findings: {key_findings}
            
            Please create a concise executive summary that includes:
            1. Overall assessment
            2. Critical differences identified
            3. Risk implications
            4. Priority recommendations
            5. Next steps
            
            Keep the summary under 500 words and suitable for executive audiences.
            """,
            
            'remediation_recommendations': """
            Based on the following audit findings, provide detailed remediation recommendations:
            
            Findings: {findings}
            
            Gaps Identified: {gaps}
            
            Please provide:
            1. Immediate actions required
            2. Short-term improvements (1-3 months)
            3. Long-term strategic changes (6-12 months)
            4. Resource requirements
            5. Success metrics
            
            Return response in JSON format with clear action items.
            """
        }
    
    async def detect_material_weaknesses(self, text: str) -> Dict[str, Any]:
        """Detect material weaknesses in audit report"""
        try:
            prompt = self.audit_prompts['material_weakness_detection'].format(text=text[:4000])
            
            response = await openai.ChatCompletion.acreate(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are an expert internal audit specialist with deep knowledge of SOX compliance and internal controls.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            return {
                'success': True,
                'material_weaknesses': result,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Material weakness detection error: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to detect material weaknesses: {str(e)}'
            }
    
    async def analyze_compliance_gaps(self, internal_report: str, external_report: str) -> Dict[str, Any]:
        """Analyze compliance gaps between internal and external reports"""
        try:
            prompt = self.audit_prompts['compliance_gap_analysis'].format(
                internal_report=internal_report[:2000],
                external_report=external_report[:2000]
            )
            
            response = await openai.ChatCompletion.acreate(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are a compliance expert specializing in regulatory gap analysis.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2500
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            return {
                'success': True,
                'compliance_gaps': result,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Compliance gap analysis error: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to analyze compliance gaps: {str(e)}'
            }
    
    async def categorize_risks(self, text: str) -> Dict[str, Any]:
        """Categorize risks found in audit report"""
        try:
            prompt = self.audit_prompts['risk_categorization'].format(text=text[:3500])
            
            response = await openai.ChatCompletion.acreate(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are a risk management expert with extensive experience in enterprise risk assessment.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            return {
                'success': True,
                'risk_categories': result,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Risk categorization error: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to categorize risks: {str(e)}'
            }
    
    async def generate_executive_summary(self, comparison_data: Dict[str, Any], key_findings: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary for audit comparison"""
        try:
            prompt = self.audit_prompts['executive_summary_generation'].format(
                comparison_data=json.dumps(comparison_data, indent=2)[:2000],
                key_findings=json.dumps(key_findings, indent=2)[:1500]
            )
            
            response = await openai.ChatCompletion.acreate(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are an executive communications specialist with expertise in audit reporting.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            
            return {
                'success': True,
                'executive_summary': content,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Executive summary generation error: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to generate executive summary: {str(e)}'
            }
    
    async def generate_remediation_recommendations(self, findings: Dict[str, Any], gaps: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed remediation recommendations"""
        try:
            prompt = self.audit_prompts['remediation_recommendations'].format(
                findings=json.dumps(findings, indent=2)[:2000],
                gaps=json.dumps(gaps, indent=2)[:1500]
            )
            
            response = await openai.ChatCompletion.acreate(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are a management consultant specializing in audit remediation and process improvement.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            return {
                'success': True,
                'recommendations': result,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Remediation recommendations error: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to generate recommendations: {str(e)}'
            }
    
    async def process_audit_workflow(self, report_text: str, workflow_type: str) -> Dict[str, Any]:
        """Process complete audit analysis workflow"""
        try:
            results = {}
            
            # Step 1: Extract key findings
            findings = await self.ai_service.extract_key_findings(report_text)
            results['key_findings'] = findings
            
            # Step 2: Detect material weaknesses
            material_weaknesses = await self.detect_material_weaknesses(report_text)
            results['material_weaknesses'] = material_weaknesses
            
            # Step 3: Categorize risks
            risk_categories = await self.categorize_risks(report_text)
            results['risk_categories'] = risk_categories
            
            # Step 4: Assess overall risk profile
            risk_profile = await self.ai_service.assess_risk_profile(report_text)
            results['risk_profile'] = risk_profile
            
            return {
                'success': True,
                'workflow_type': workflow_type,
                'results': results,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Audit workflow processing error: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to process audit workflow: {str(e)}'
            }
    
    async def batch_process_reports(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process multiple reports in batch"""
        results = []
        
        for report in reports:
            try:
                result = await self.process_audit_workflow(
                    report['text'], 
                    report.get('workflow_type', 'standard')
                )
                results.append({
                    'report_id': report.get('id'),
                    'result': result
                })
                
                # Add delay to prevent rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f'Batch processing error for report {report.get("id")}: {str(e)}')
                results.append({
                    'report_id': report.get('id'),
                    'result': {
                        'success': False,
                        'error': f'Processing failed: {str(e)}'
                    }
                })
        
        return results
    
    def get_optimal_model(self, task_type: str, text_length: int) -> str:
        """Determine optimal model based on task and text length"""
        if task_type in ['complex_analysis', 'detailed_comparison', 'risk_assessment']:
            return 'gpt-4'
        elif text_length > 3000:
            return 'gpt-4'
        else:
            return 'gpt-3.5-turbo'

# Initialize LLM service
llm_service = LLMService()
