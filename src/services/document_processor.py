import os
import hashlib
import PyPDF2
import docx
from typing import Dict, Any, Optional
from pathlib import Path
import magic
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Service for processing uploaded audit documents"""
    
    SUPPORTED_FORMATS = {
        'application/pdf': '.pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'text/plain': '.txt'
    }
    
    def __init__(self, upload_dir: str = 'uploads'):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """Validate uploaded file format and size"""
        try:
            file_path = Path(file_path)
            
            # Check if file exists
            if not file_path.exists():
                return {'valid': False, 'error': 'File not found'}
            
            # Get file size
            file_size = file_path.stat().st_size
            
            # Check file size (max 50MB)
            if file_size > 50 * 1024 * 1024:
                return {'valid': False, 'error': 'File too large (max 50MB)'}
            
            # Check MIME type
            mime_type = magic.from_file(str(file_path), mime=True)
            
            if mime_type not in self.SUPPORTED_FORMATS:
                return {
                    'valid': False, 
                    'error': f'Unsupported file format: {mime_type}'
                }
            
            return {
                'valid': True,
                'file_size': file_size,
                'mime_type': mime_type,
                'extension': self.SUPPORTED_FORMATS[mime_type]
            }
            
        except Exception as e:
            logger.error(f'File validation error: {str(e)}')
            return {'valid': False, 'error': f'Validation error: {str(e)}'}
    
    def calculate_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            text = ''
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + '\n'
            return text.strip()
        except Exception as e:
            logger.error(f'PDF text extraction error: {str(e)}')
            raise ValueError(f'Failed to extract text from PDF: {str(e)}')
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n'.join(text)
        except Exception as e:
            logger.error(f'DOCX text extraction error: {str(e)}')
            raise ValueError(f'Failed to extract text from DOCX: {str(e)}')
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f'TXT text extraction error: {str(e)}')
            raise ValueError(f'Failed to extract text from TXT: {str(e)}')
    
    def extract_text(self, file_path: str, mime_type: str) -> str:
        """Extract text based on file type"""
        if mime_type == 'application/pdf':
            return self.extract_text_from_pdf(file_path)
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            return self.extract_text_from_docx(file_path)
        elif mime_type == 'text/plain':
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f'Unsupported MIME type: {mime_type}')
    
    def process_document(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Process uploaded document and extract metadata"""
        try:
            # Validate file
            validation = self.validate_file(file_path)
            if not validation['valid']:
                return validation
            
            # Calculate file hash
            file_hash = self.calculate_hash(file_path)
            
            # Extract text content
            raw_text = self.extract_text(file_path, validation['mime_type'])
            
            # Basic text analysis
            word_count = len(raw_text.split())
            char_count = len(raw_text)
            
            return {
                'valid': True,
                'file_size': validation['file_size'],
                'mime_type': validation['mime_type'],
                'file_hash': file_hash,
                'raw_text': raw_text,
                'metadata': {
                    'original_filename': original_filename,
                    'word_count': word_count,
                    'char_count': char_count,
                    'processed_at': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f'Document processing error: {str(e)}')
            return {'valid': False, 'error': f'Processing error: {str(e)}'}

# Initialize document processor
document_processor = DocumentProcessor()
