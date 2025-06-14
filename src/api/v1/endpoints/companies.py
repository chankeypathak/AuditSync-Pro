from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from src.core.database import get_db
from src.models.pydantic_models import CompanyCreate, CompanyUpdate, CompanyResponse
from src.models import Company
from src.services.comparison_service import comparison_service

router = APIRouter()
security = HTTPBearer()

@router.post('/', response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    db: Session = Depends(get_db),
    token: str = Depends(security)
):
    """Create a new company"""
    try:
        # Check if company already exists
        existing_company = db.query(Company).filter(
            Company.name == company_data.name
        ).first()
        
        if existing_company:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Company with this name already exists'
            )
        
        # Create new company
        company = Company(**company_data.dict())
        db.add(company)
        db.commit()
        db.refresh(company)
        
        return company
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to create company: {str(e)}'
        )

@router.get('/', response_model=List[CompanyResponse])
async def get_companies(
    skip: int = 0,
    limit: int = 100,
    sector: Optional[str] = None,
    db: Session = Depends(get_db),
    token: str = Depends(security)
):
    """Get list of companies"""
    try:
        query = db.query(Company)
        
        if sector:
            query = query.filter(Company.sector == sector)
        
        companies = query.offset(skip).limit(limit).all()
        return companies
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to retrieve companies: {str(e)}'
        )

@router.get('/{company_id}', response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    token: str = Depends(security)
):
    """Get company by ID"""
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Company not found'
            )
        
        return company
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to retrieve company: {str(e)}'
        )

@router.put('/{company_id}', response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    company_data: CompanyUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(security)
):
    """Update company information"""
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Company not found'
            )
        
        # Update fields
        update_data = company_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)
        
        db.commit()
        db.refresh(company)
        
        return company
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to update company: {str(e)}'
        )

@router.delete('/{company_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    token: str = Depends(security)
):
    """Delete company"""
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Company not found'
            )
        
        db.delete(company)
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to delete company: {str(e)}'
        )

@router.get('/{company_id}/stats')
async def get_company_stats(
    company_id: UUID,
    db: Session = Depends(get_db),
    token: str = Depends(security)
):
    """Get company statistics"""
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Company not found'
            )
        
        # Get comparison statistics
        comparison_stats = comparison_service.get_comparison_stats(db, company_id)
        
        # Get report count
        report_count = len(company.audit_reports)
        
        return {
            'company_id': company_id,
            'total_reports': report_count,
            'comparison_stats': comparison_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to retrieve company stats: {str(e)}'
        )
