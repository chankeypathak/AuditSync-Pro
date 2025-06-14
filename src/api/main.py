from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
import uvicorn
from contextlib import asynccontextmanager

from src.api.routes import audit_routes, comparison_routes, dashboard_routes
from src.core.config import settings
from src.core.database import init_db
from src.core.logging_config import setup_logging
from src.services.monitoring import setup_monitoring

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    await init_db()
    setup_monitoring()
    yield
    # Shutdown
    pass

app = FastAPI(
    title="Audit Report Comparison GenAI API",
    description="AI-powered audit report comparison and analysis system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(audit_routes.router, prefix="/api/v1/audit", tags=["audit"])
app.include_router(comparison_routes.router, prefix="/api/v1/comparison", tags=["comparison"])
app.include_router(dashboard_routes.router, prefix="/api/v1/dashboard", tags=["dashboard"])

@app.get("/")
async def root():
    return {"message": "Audit Report Comparison GenAI API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
