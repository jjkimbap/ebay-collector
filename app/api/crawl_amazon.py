"""
Amazon 크롤링 API
"""
from typing import Optional

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.crawl_service import crawl_amazon_for_customer, crawl_amazon_batch
from app.services.keyword_service import get_customer_keywords

logger = structlog.get_logger()

router = APIRouter(prefix="/api/crawl/amazon", tags=["crawl"])


class CrawlAmazonResponse(BaseModel):
    """크롤링 응답 모델"""
    success: bool
    total_keywords: Optional[int] = None
    total_items: Optional[int] = None
    saved_items: Optional[int] = None
    errors: Optional[list[str]] = None
    error: Optional[str] = None


class CrawlAmazonBatchResponse(BaseModel):
    """배치 크롤링 응답 모델"""
    success: bool
    total_customers: Optional[int] = None
    processed_customers: Optional[int] = None
    total_keywords: Optional[int] = None
    total_items: Optional[int] = None
    saved_items: Optional[int] = None
    customer_results: Optional[list[dict]] = None
    errors: Optional[list[str]] = None
    error: Optional[str] = None


@router.get("", response_model=CrawlAmazonResponse)
async def crawl_amazon(
    customer_cd: int = Query(..., description="고객 코드"),
    price_level: int = Query(2, ge=0, le=5, description="가격 레벨 (0-5)"),
    limit: int = Query(5, ge=1, le=200, description="키워드당 수집할 상품 수 (기본값: 5)"),
):
    """
    Amazon 크롤링 API
    
    고객 키워드를 조회하고, 각 키워드로 Amazon 상품을 검색한 뒤,
    데이터를 가공하여 MongoDB에 저장합니다.
    
    **처리 흐름:**
    1. 고객 키워드 조회 (`/api/customer-keywords`)
    2. 각 키워드로 Amazon API 호출 (`/api/amazon/item_summary/search`)
    3. 응답 데이터 가공 (category split, price 구조 변경 등)
    4. MongoDB 저장 (`amazonPrices` 컬렉션)
    
    **데이터 가공 규칙:**
    - category: " > " 기준으로 split하여 배열로 변환
    - price: current, original, discount_rate 구조로 변환
    - reviews: 문자열을 정수로 변환
    - image: image.imageUrl 추출
    - create_date: 현재 시각 (UTC)
    - platform: "amazon" 고정
    
    """
    logger.info(
        "Amazon crawl request",
        customer_cd=customer_cd,
        price_level=price_level
    )
    
    try:
        # 크롤링 실행
        result = await crawl_amazon_for_customer(
            customer_cd=customer_cd,
            price_level=price_level,
            limit=limit,
        )
        
        if not result.get("success"):
            return CrawlAmazonResponse(
                success=False,
                error=result.get("error", "Unknown error"),
            )
        
        return CrawlAmazonResponse(
            success=True,
            total_keywords=result.get("total_keywords"),
            total_items=result.get("total_items"),
            saved_items=result.get("saved_items"),
            errors=result.get("errors") if result.get("errors") else None,
        )
        
    except Exception as e:
        logger.error(
            "Failed to crawl Amazon",
            error=str(e),
            customer_cd=customer_cd,
            price_level=price_level,
            exc_info=True
        )
        return CrawlAmazonResponse(
            success=False,
            error=f"Failed to crawl Amazon: {str(e)}",
        )


@router.get("/batch", response_model=CrawlAmazonBatchResponse)
async def crawl_amazon_batch_endpoint(
    price_level: int = Query(2, ge=0, le=5, description="가격 레벨 (0-5)"),
    limit: int = Query(5, ge=1, le=200, description="키워드당 수집할 상품 수 (기본값: 5)"),
):
    """
    Amazon 배치 크롤링 API
    
    특정 price_level의 모든 고객에 대해 크롤링을 실행합니다.
    
    **처리 흐름:**
    1. price_level로 모든 고객 조회 (customer_cd 리스트)
    2. 각 customer_cd에 대해 크롤링 실행
    3. 결과 집계 및 반환
    
    """
    logger.info(
        "Amazon batch crawl request",
        price_level=price_level
    )
    
    try:
        # Step 1: price_level로 모든 고객 조회
        keywords_list = await get_customer_keywords(
            customer_cd=None,  # None이면 모든 고객 조회
            price_level=price_level
        )
        
        if not keywords_list:
            return CrawlAmazonBatchResponse(
                success=False,
                error=f"No customers found for price_level={price_level}",
            )
        
        # customer_cd 리스트 추출
        customer_cds = [kw.customerCd for kw in keywords_list if kw.customerCd]
        
        if not customer_cds:
            return CrawlAmazonBatchResponse(
                success=False,
                error="No valid customer_cd found",
            )
        
        logger.info(
            "Customers retrieved for batch crawl",
            price_level=price_level,
            customer_count=len(customer_cds),
            customer_cds=customer_cds
        )
        
        # Step 2: 각 customer_cd에 대해 크롤링 실행
        result = await crawl_amazon_batch(
            customer_cds=customer_cds,
            price_level=price_level,
            limit=limit,
        )
        
        if not result.get("success"):
            return CrawlAmazonBatchResponse(
                success=False,
                error=result.get("error", "Unknown error"),
            )
        
        return CrawlAmazonBatchResponse(
            success=True,
            total_customers=result.get("total_customers"),
            processed_customers=result.get("processed_customers"),
            total_keywords=result.get("total_keywords"),
            total_items=result.get("total_items"),
            saved_items=result.get("saved_items"),
            customer_results=result.get("customer_results"),
            errors=result.get("errors") if result.get("errors") else None,
        )
        
    except Exception as e:
        logger.error(
            "Failed to crawl Amazon batch",
            error=str(e),
            price_level=price_level,
            exc_info=True
        )
        return CrawlAmazonBatchResponse(
            success=False,
            error=f"Failed to crawl Amazon batch: {str(e)}",
        )
