from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "Audit Report Comparison GenAI"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # API settings
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/audit_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    
    # LLM Settings
    OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2023-05-15"
    DEFAULT_LLM_MODEL: str = "gpt-4-turbo-preview"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.1
    
    # Vector Database
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: str = "us-west1-gcp"
    PINECONE_INDEX_NAME: str = "audit-reports"
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    VECTOR_DIMENSION: int = 1536
    
    # MLOps
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    WANDB_API_KEY: Optional[str] = None
    WANDB_PROJECT: str = "audit-genai"
    MODEL_REGISTRY_PATH: str = "./models"
    
    # Data paths
    DATA_PATH: Path = Path("./data")
    UPLOAD_PATH: Path = Path("./data/uploads")
    PROCESSED_PATH: Path = Path("./data/processed")
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # External APIs
    SEC_EDGAR_API_KEY: Optional[str] = None
    SEC_EDGAR_BASE_URL: str = "https://data.sec.gov"
    
    # Monitoring
    PROMETHEUS_PORT: int = 8001
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
