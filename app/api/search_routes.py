"""
검색 기반 가격 수집 API 라우트

브랜드명이나 키워드로 eBay 상품을 검색하고 가격 정보를 수집합니다.
"""
from decimal import Decimal
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.ebay.search_collector import (
    EbaySearchCollector,
    SearchResult,
    create_mock_search_result,
)
from app.core.config import get_settings
from app.core.database import get_db

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(prefix="/api/v1/search", tags=["search"])


# ==================== Request/Response Models ====================

class SearchRequest(BaseModel):
    """검색 요청 모델"""
    query: str = Field(..., min_length=1, max_length=200, description="검색 키워드 (예: '3ce', '3ce lipstick')")
    category: Optional[str] = Field(None, description="카테고리 (예: 'makeup', 'skincare', 'electronics')")
    min_price: Optional[Decimal] = Field(None, ge=0, description="최소 가격 (USD)")
    max_price: Optional[Decimal] = Field(None, ge=0, description="최대 가격 (USD)")
    condition: Optional[str] = Field(None, description="상품 상태: new, used, refurbished")
    sort: str = Field("best_match", description="정렬: price, price_desc, date, best_match")
    limit: int = Field(50, ge=1, le=200, description="결과 수 (최대 200)")
    page: int = Field(1, ge=1, description="페이지 번호")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "3ce",
                    "limit": 50
                },
                {
                    "query": "3ce lipstick",
                    "category": "makeup",
                    "max_price": 30.00,
                    "sort": "price",
                    "limit": 100
                }
            ]
        }
    }


class SearchItemResponse(BaseModel):
    """검색 결과 개별 아이템"""
    item_id: str
    title: str
    price: float
    currency: str
    shipping_fee: float
    total_price: float
    condition: str
    listing_type: str
    seller_name: Optional[str]
    image_url: Optional[str]
    item_url: Optional[str]
    bid_count: Optional[int]


class PriceStats(BaseModel):
    """가격 통계"""
    min_price: float
    max_price: float
    avg_price: float
    item_count: int


class SearchResponse(BaseModel):
    """검색 응답 모델"""
    success: bool
    query: str
    total_count: int
    items: list[SearchItemResponse]
    price_stats: Optional[PriceStats]
    page: int
    page_size: int
    has_more: bool
    search_url: Optional[str]
    collection_method: str
    error: Optional[str] = None


# ==================== API Endpoints ====================

@router.post("", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """
    eBay 상품 검색
    
    브랜드명이나 키워드로 상품을 검색하고 가격 정보를 수집합니다.
    
    **사용 예시:**
    - 브랜드 검색: `{"query": "3ce"}`
    - 상세 검색: `{"query": "3ce lipstick", "category": "makeup", "max_price": 30}`
    - 가격순 정렬: `{"query": "3ce", "sort": "price"}`
    
    **참고:** eBay API 키가 설정되어 있어야 합니다.
    """
    logger.info("Search request", query=request.query, category=request.category)
    
    # API 키 체크
    if not settings.ebay_api_configured:
        # API 키가 없으면 모의 데이터 반환 (개발/테스트용)
        logger.warning("eBay API not configured, returning mock data")
        mock_result = create_mock_search_result(request.query)
        return _convert_to_response(mock_result, is_mock=True)
    
    # 실제 검색 수행
    collector = EbaySearchCollector()
    try:
        result = await collector.search(
            query=request.query,
            category=request.category,
            min_price=request.min_price,
            max_price=request.max_price,
            condition=request.condition,
            sort=request.sort,
            limit=request.limit,
            page=request.page,
        )
        
        return _convert_to_response(result)
        
    finally:
        await collector.close()


@router.get("/brand/{brand_name}", response_model=SearchResponse)
async def search_by_brand(
    brand_name: str,
    category: Optional[str] = Query(None, description="카테고리 필터"),
    limit: int = Query(50, ge=1, le=200, description="결과 수"),
):
    """
    브랜드명으로 검색
    
    **사용 예시:**
    - GET /api/v1/search/brand/3ce
    - GET /api/v1/search/brand/MAC?category=makeup&limit=100
    """
    logger.info("Brand search", brand=brand_name, category=category)
    
    if not settings.ebay_api_configured:
        mock_result = create_mock_search_result(brand_name)
        return _convert_to_response(mock_result, is_mock=True)
    
    collector = EbaySearchCollector()
    try:
        result = await collector.search_brand(
            brand=brand_name,
            category=category,
            limit=limit,
        )
        return _convert_to_response(result)
    finally:
        await collector.close()


@router.get("/categories")
async def get_supported_categories():
    """
    지원되는 카테고리 목록 조회
    
    검색 시 category 파라미터에 사용할 수 있는 값들입니다.
    """
    return {
        "categories": {
            "makeup": {"id": "31786", "name": "Makeup"},
            "cosmetics": {"id": "31786", "name": "Cosmetics"},
            "beauty": {"id": "26395", "name": "Beauty"},
            "skincare": {"id": "11863", "name": "Skincare"},
            "electronics": {"id": "293", "name": "Electronics"},
            "phones": {"id": "9355", "name": "Cell Phones"},
            "computers": {"id": "58058", "name": "Computers"},
            "clothing": {"id": "11450", "name": "Clothing"},
            "shoes": {"id": "93427", "name": "Shoes"},
        },
        "note": "You can also use eBay category ID directly"
    }


@router.post("/bulk", response_model=SearchResponse)
async def bulk_search(
    request: SearchRequest,
    max_items: int = Query(500, ge=1, le=1000, description="최대 수집 아이템 수"),
):
    """
    대량 검색 (여러 페이지 자동 수집)
    
    여러 페이지에 걸쳐 최대 max_items 개까지 상품을 수집합니다.
    
    **주의:** 많은 API 호출이 발생할 수 있으므로 rate limit에 주의하세요.
    """
    logger.info("Bulk search", query=request.query, max_items=max_items)
    
    if not settings.ebay_api_configured:
        mock_result = create_mock_search_result(request.query)
        return _convert_to_response(mock_result, is_mock=True)
    
    collector = EbaySearchCollector()
    try:
        result = await collector.collect_all_pages(
            query=request.query,
            max_items=max_items,
            category=request.category,
            min_price=request.min_price,
            max_price=request.max_price,
            condition=request.condition,
            sort=request.sort,
        )
        return _convert_to_response(result)
    finally:
        await collector.close()


# ==================== Helper Functions ====================

def _convert_to_response(result: SearchResult, is_mock: bool = False) -> SearchResponse:
    """SearchResult를 API 응답 형식으로 변환"""
    items = [
        SearchItemResponse(
            item_id=item.item_id,
            title=item.title,
            price=float(item.price),
            currency=item.currency,
            shipping_fee=float(item.shipping_fee),
            total_price=float(item.total_price),
            condition=item.condition,
            listing_type=item.listing_type,
            seller_name=item.seller_name,
            image_url=item.image_url,
            item_url=item.item_url,
            bid_count=item.bid_count,
        )
        for item in result.items
    ]
    
    # 가격 통계
    price_stats = None
    if result.items:
        stats = result.price_stats
        price_stats = PriceStats(
            min_price=float(stats["min_price"]),
            max_price=float(stats["max_price"]),
            avg_price=round(float(stats["avg_price"]), 2),
            item_count=stats["item_count"],
        )
    
    error_msg = result.error_message
    if is_mock and not error_msg:
        error_msg = "API not configured. Showing mock data for demonstration."
    
    return SearchResponse(
        success=result.success,
        query=result.query,
        total_count=result.total_count,
        items=items,
        price_stats=price_stats,
        page=result.page,
        page_size=result.page_size,
        has_more=result.has_more,
        search_url=result.search_url,
        collection_method=result.collection_method,
        error=error_msg,
    )
