import openai
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sentence_transformers import SentenceTransformer
import json
import logging
from datetime import datetime
from src.core.config import settings

logger = logging.getLogger(__name__)

class AIService:
    """Service for AI-powered audit report analysis and comparison"""
    
    def __init__(self):
        # Initialize OpenAI client
        openai.api_key = settings.OPENAI_API_KEY
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Define audit-specific prompts
        self.prompts = {
            'extract_findings': """
            Analyze the following audit report and extract key findings:
            
            Report Text: {text}
            
            Please extract and categorize the following:
            1. Material weaknesses
            2. Significant deficiencies
            3. Risk assessments
            4. Compliance issues
            5. Recommendations
            
            Return the response in JSON format with clear categorization.
            """,
            
            'compare_reports': """
            Compare these two audit reports and identify key differences:
            
            Report A (Source): {report_a}
            
            Report B (Target): {report_b}
            
            Please provide:
            1. Similarity score (0-100)
            2. Key differences
            3. Risk alignment assessment
            4. Compliance gaps
            5. Recommendations for reconciliation
            
            Return the response in JSON format.
            """,
            
            'risk_assessment': """
            Assess the risk profile of this audit report:
            
            Report Text: {text}
            
            Please evaluate:
            1. Overall risk level (Low/Medium/High)
            2. Risk categories identified
            3. Control effectiveness
            4. Materiality assessment
            5. Regulatory compliance status
            
            Return the response in JSON format.
            """
        }
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for text using sentence transformer"""
        try:
            # Clean and truncate text if necessary
            cleaned_text = self._clean_text(text)
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(cleaned_text)
            
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f'Embedding generation error: {str(e)}')
            raise ValueError(f'Failed to generate embeddings: {str(e)}')
    
    async def extract_key_findings(self, text: str) -> Dict[str, Any]:
        """Extract key findings from audit report using GPT"""
        try:
            prompt = self.prompts['extract_findings'].format(text=text[:4000])  # Limit text length
            
            response = await openai.ChatCompletion.acreate(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are an expert audit analyst.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            # Parse JSON response
            content = response.choices[0].message.content
            findings = json.loads(content)
            
            return findings
            
        except Exception as e:
            logger.error(f'Key findings extraction error: {str(e)}')
            return {'error': f'Failed to extract findings: {str(e)}'}
    
    async def compare_reports(self, report_a: str, report_b: str) -> Dict[str, Any]:
        """Compare two audit reports using GPT"""
        try:
            # Truncate reports if too long
            report_a_truncated = report_a[:2000]
            report_b_truncated = report_b[:2000]
            
            prompt = self.prompts['compare_reports'].format(
                report_a=report_a_truncated,
                report_b=report_b_truncated
            )
            
            response = await openai.ChatCompletion.acreate(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are an expert audit analyst specializing in report comparison.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            # Parse JSON response
            content = response.choices[0].message.content
            comparison = json.loads(content)
            
            return comparison
            
        except Exception as e:
            logger.error(f'Report comparison error: {str(e)}')
            return {'error': f'Failed to compare reports: {str(e)}'}
    
    async def assess_risk_profile(self, text: str) -> Dict[str, Any]:
        """Assess risk profile of audit report"""
        try:
            prompt = self.prompts['risk_assessment'].format(text=text[:3000])
            
            response = await openai.ChatCompletion.acreate(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are an expert risk assessment analyst.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse JSON response
            content = response.choices[0].message.content
            risk_assessment = json.loads(content)
            
            return risk_assessment
            
        except Exception as e:
            logger.error(f'Risk assessment error: {str(e)}')
            return {'error': f'Failed to assess risk: {str(e)}'}
    
    def calculate_similarity(self, embeddings_a: List[float], embeddings_b: List[float]) -> float:
        """Calculate cosine similarity between two embedding vectors"""
        try:
            vec_a = np.array(embeddings_a)
            vec_b = np.array(embeddings_b)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec_a, vec_b)
            norm_a = np.linalg.norm(vec_a)
            norm_b = np.linalg.norm(vec_b)
            
            similarity = dot_product / (norm_a * norm_b)
            
            # Convert to 0-1 scale
            return float((similarity + 1) / 2)
            
        except Exception as e:
            logger.error(f'Similarity calculation error: {str(e)}')
            return 0.0
    
    def _clean_text(self, text: str) -> str:
        """Clean and preprocess text for AI analysis"""
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove special characters that might interfere
        text = text.replace('\x00', '')
        
        # Limit length to prevent token overflow
        if len(text) > 8000:
            text = text[:8000] + '...'
        
        return text
    
    async def batch_process_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Process multiple texts for embeddings in batches"""
        try:
            embeddings = []
            
            # Process in batches to avoid memory issues
            batch_size = 10
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                cleaned_batch = [self._clean_text(text) for text in batch]
                
                # Generate embeddings for batch
                batch_embeddings = self.embedding_model.encode(cleaned_batch)
                embeddings.extend(batch_embeddings.tolist())
                
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.1)
            
            return embeddings
            
        except Exception as e:
            logger.error(f'Batch embedding processing error: {str(e)}')
            raise ValueError(f'Failed to process batch embeddings: {str(e)}')

# Initialize AI service
ai_service = AIService()
