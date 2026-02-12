"""
Customer Keywords API endpoints.
"""
from typing import Optional

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.schemas.customer_keyword import CustomerKeyword
from app.services.keyword_service import get_customer_keywords

logger = structlog.get_logger()

router = APIRouter(prefix="/api/customer-keywords", tags=["customer-keywords"])


class CustomerKeywordsResponse(BaseModel):
    """Response model for customer keywords."""
    success: bool
    total: Optional[int] = None
    items: Optional[list[CustomerKeyword]] = None
    error: Optional[str] = None


@router.get("", response_model=CustomerKeywordsResponse)
async def get_keywords(
    customer_cd: Optional[int] = Query(None, description="고객 코드 (지정 시 해당 고객만 조회)"),
    price_level: int = Query(2, ge=0, le=5, description="가격 레벨 (0-5)"),
):
    """
    고객 키워드 조회 API
    
    `customer_cd`와 `price_level`을 통해 고객의 키워드 정보를 조회합니다.
    
    - **customer_cd**: 고객 코드 (선택사항, 지정하지 않으면 모든 고객 조회)
    - **price_level**: 가격 레벨 (기본값: 2)
    
    **예시:**
    - 모든 고객 조회: `/api/customer-keywords?price_level=2`
    - 특정 고객 조회: `/api/customer-keywords?customer_cd=123&price_level=2`
    """
    logger.info(
        "Customer keywords request",
        customer_cd=customer_cd,
        price_level=price_level
    )
    
    try:
        keywords = await get_customer_keywords(
            customer_cd=customer_cd,
            price_level=price_level
        )
        
        return CustomerKeywordsResponse(
            success=True,
            total=len(keywords),
            items=keywords if keywords else None,
        )
    except Exception as e:
        logger.error(
            "Failed to fetch customer keywords",
            error=str(e),
            customer_cd=customer_cd,
            price_level=price_level,
            exc_info=True
        )
        return CustomerKeywordsResponse(
            success=False,
            error=f"Failed to fetch customer keywords: {str(e)}"
        )
