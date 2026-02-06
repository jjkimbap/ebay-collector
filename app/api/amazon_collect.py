"""
Amazon 상품 검색 API
"""
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.lib.commerce_playwright import search_items

logger = structlog.get_logger()

router = APIRouter(prefix="/api/amazon/item_summary/search", tags=["amazon"])


class SearchItemResponse(BaseModel):
    """검색 결과 개별 아이템"""
    model_config = ConfigDict(extra="allow")  # 추가 필드 허용
    
    itemId: Optional[str] = None  # ASIN (Amazon Standard Identification Number)
    title: Optional[str] = None
    price: Optional[dict[str, Any]] = None  # 현재 가격
    originalPrice: Optional[dict[str, Any]] = None  # 원래 가격 (할인 전)
    discount: Optional[str] = None  # 할인율 (예: "25%")
    rating: Optional[str] = None  # 평점 (예: "4.5")
    reviews: Optional[str] = None  # 리뷰 수 (예: "1,234")
    condition: Optional[str] = None  # 상품 상태 (예: "New", "Used")
    category: Optional[str] = None  # 카테고리 (예: "Beauty & Personal Care > Makeup")
    image: Optional[dict[str, Any]] = None
    itemWebUrl: Optional[str] = None


class SearchResponse(BaseModel):
    """검색 응답 모델"""
    success: bool
    total: Optional[int] = None
    itemSummaries: Optional[list[SearchItemResponse]] = None
    error: Optional[str] = None


@router.get("", response_model=SearchResponse)
async def search_products(
    keyword: str = Query(..., description="검색 키워드"),
    limit: int = Query(3, ge=1, le=200, description="결과 수 (최대 200)"),
):
    """
    Amazon 상품 검색 API
    
    Playwright를 사용하여 상품을 검색합니다.
    
    **필터링:**
    - 상품 제목에 검색 키워드가 포함된 상품만 수집합니다.
    - 키워드가 여러 단어인 경우, 주요 단어들이 제목에 포함된 상품을 수집합니다.
    
    **설정:**
    - PLAYWRIGHT_HEADLESS
    - PLAYWRIGHT_PROXY (선택)
    - PLAYWRIGHT_AMAZON_DOMAIN (기본값: com)
    
    **수집 정보:**
    - 상품 제목, 가격, 원래 가격, 할인율
    - 평점, 리뷰 수
    - 카테고리
    - 상품 이미지, 링크
    - ASIN (Amazon Standard Identification Number)
    """
    logger.info("Amazon search request", query=keyword, limit=limit)

    result = await search_items("amazon", keyword, limit)
    if not result.get("success"):
        return SearchResponse(success=False, error=result.get("error", "Unknown error"))

    item_summaries = [SearchItemResponse(**item) for item in result.get("items", [])]
    # total은 필터링 후 실제로 수집된 아이템 수 (제목에 키워드가 포함된 상품 수)
    total_count = len(item_summaries)
    return SearchResponse(
        success=True,
        total=total_count,
        itemSummaries=item_summaries if item_summaries else None,
    )

