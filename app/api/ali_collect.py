"""
AliExpress 상품 검색 API
"""
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.lib.commerce_playwright import search_items

logger = structlog.get_logger()

router = APIRouter(prefix="/api/ali/item_summary/search", tags=["ali"])


class SearchItemResponse(BaseModel):
    """검색 결과 개별 아이템"""
    model_config = ConfigDict(extra="allow")  # 추가 필드 허용
    
    itemId: Optional[str] = None
    title: Optional[str] = None
    price: Optional[dict[str, Any]] = None  # 현재 가격 (할인된 가격)
    originalPrice: Optional[dict[str, Any]] = None  # 원래 가격
    discount: Optional[str] = None  # 할인율 (예: "85%")
    rating: Optional[str] = None  # 평점 (예: "4.8")
    sales: Optional[str] = None  # 판매량 (예: "900+", "1.2k")
    condition: Optional[str] = None
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
    AliExpress 상품 검색 API
    
    Playwright를 사용하여 상품을 검색합니다.
    
    **설정:**
    - PLAYWRIGHT_HEADLESS
    - PLAYWRIGHT_PROXY (선택)
    """
    logger.info("AliExpress search request", query=keyword, limit=limit)

    result = await search_items("aliexpress", keyword, limit)
    if not result.get("success"):
        return SearchResponse(success=False, error=result.get("error", "Unknown error"))

    item_summaries = [SearchItemResponse(**item) for item in result.get("items", [])]
    return SearchResponse(
        success=True,
        total=result.get("total", len(item_summaries)),
        itemSummaries=item_summaries if item_summaries else None,
    )

