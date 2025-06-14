from fastapi import APIRouter
from src.api.v1.endpoints import companies, reports, comparisons, users, tasks

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(companies.router, prefix='/companies', tags=['companies'])
api_router.include_router(reports.router, prefix='/reports', tags=['reports'])
api_router.include_router(comparisons.router, prefix='/comparisons', tags=['comparisons'])
api_router.include_router(users.router, prefix='/users', tags=['users'])
api_router.include_router(tasks.router, prefix='/tasks', tags=['tasks'])
