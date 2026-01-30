"""
API routes for price collection.
"""
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import CollectorRegistry
from app.collectors.ebay import EbayCollector
from app.core.database import get_db
from app.models.database import StoreType
from app.models.schemas import (
    CollectPriceRequest,
    CollectPriceResponse,
    PriceHistoryResponse,
    TrackItemRequest,
    TrackItemResponse,
    UrlParseRequest,
    UrlParseResponse,
)
from app.services.currency import get_currency_service
from app.services.price_history import PriceHistoryService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["price"])


@router.post("/parse-url", response_model=UrlParseResponse)
async def parse_url(request: UrlParseRequest):
    """
    상품 URL을 파싱하여 스토어 식별자를 추출합니다.
    
    다양한 형식의 eBay URL을 지원합니다:
    - `https://www.ebay.com/itm/256123456789`
    - `https://www.ebay.com/itm/product-title/256123456789`
    
    **응답 예시:**
    ```json
    {
        "success": true,
        "store": "ebay",
        "item_id": "256123456789",
        "original_url": "https://www.ebay.com/itm/256123456789",
        "canonical_url": "https://www.ebay.com/itm/256123456789"
    }
    ```
    """
    url = str(request.url)
    
    # Find appropriate collector
    collector = CollectorRegistry.get_collector_for_url(url)
    
    if not collector:
        return UrlParseResponse(
            success=False,
            original_url=url,
            error="Unsupported store URL. Currently only eBay is supported."
        )
    
    return await collector.parse_url(url)


@router.post("/collect", response_model=CollectPriceResponse)
async def collect_price(
    request: CollectPriceRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    상품 URL의 현재 가격을 수집합니다.
    
    eBay에서 가격 정보를 가져와 정규화합니다.
    
    **응답 예시:**
    ```json
    {
        "success": true,
        "data": {
            "store": "ebay",
            "item_id": "256123456789",
            "metadata": {
                "title": "Apple iPhone 14 Pro 256GB",
                "seller_name": "tech_seller",
                "condition": "new",
                "listing_type": "buy_it_now"
            },
            "price_data": {
                "price": 999.99,
                "shipping_fee": 12.00,
                "currency": "USD",
                "total_price": 1011.99
            },
            "collected_at": "2024-01-30T12:00:00Z",
            "collection_method": "api"
        },
        "cached": false
    }
    ```
    """
    url = str(request.url)
    
    # Find collector
    collector = CollectorRegistry.get_collector_for_url(url)
    
    if not collector:
        return CollectPriceResponse(
            success=False,
            error="Unsupported store URL"
        )
    
    # Parse URL
    parse_result = await collector.parse_url(url)
    if not parse_result.success:
        return CollectPriceResponse(
            success=False,
            error=parse_result.error
        )
    
    # Build identifier
    from app.models.schemas import EbayIdentifier
    identifier = EbayIdentifier(item_id=parse_result.item_id)
    
    # Collect price
    result = await collector.collect_price(identifier)
    
    if not result.success:
        return CollectPriceResponse(
            success=False,
            data=result,
            error=result.error_message
        )
    
    # Normalize currency if needed
    if result.price_data and result.price_data.currency != "USD":
        currency_service = get_currency_service()
        result.normalized_price = await currency_service.normalize_price(
            result.price_data
        )
    
    # Save to history
    try:
        history_service = PriceHistoryService(db)
        await history_service.save_price(result)
        await history_service.get_or_create_tracked_item(result, url)
    except Exception as e:
        logger.error("Failed to save price history", error=str(e))
        # Don't fail the request, just log the error
    
    return CollectPriceResponse(
        success=True,
        data=result,
        cached=False
    )


@router.post("/track", response_model=TrackItemResponse)
async def track_item(
    request: TrackItemRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    상품 가격 변동 추적을 시작합니다.
    
    목표 가격이나 가격 하락 비율을 설정하여 알림을 받을 수 있습니다.
    
    **요청 예시:**
    ```json
    {
        "url": "https://www.ebay.com/itm/256123456789",
        "notification_email": "user@example.com",
        "target_price": 800.00
    }
    ```
    
    **응답 예시:**
    ```json
    {
        "success": true,
        "tracking_id": 1,
        "item_id": "256123456789",
        "store": "ebay",
        "message": "Now tracking item: Apple iPhone 14 Pro 256GB"
    }
    ```
    """
    url = str(request.url)
    
    # Find collector
    collector = CollectorRegistry.get_collector_for_url(url)
    
    if not collector:
        return TrackItemResponse(
            success=False,
            message="Unsupported store URL"
        )
    
    # Parse URL
    parse_result = await collector.parse_url(url)
    if not parse_result.success:
        return TrackItemResponse(
            success=False,
            message=f"Failed to parse URL: {parse_result.error}"
        )
    
    # Build identifier and collect initial price
    from app.models.schemas import EbayIdentifier
    identifier = EbayIdentifier(item_id=parse_result.item_id)
    
    result = await collector.collect_price(identifier)
    
    if not result.success:
        return TrackItemResponse(
            success=False,
            message=f"Failed to collect initial price: {result.error_message}"
        )
    
    # Save to database
    history_service = PriceHistoryService(db)
    tracked_item = await history_service.get_or_create_tracked_item(result, url)
    await history_service.save_price(result)
    
    # Create alert if requested
    if request.target_price or request.price_drop_percentage:
        await history_service.create_price_alert(
            store=StoreType(result.store.value),
            item_id=result.item_id,
            target_price=request.target_price,
            price_drop_percentage=request.price_drop_percentage,
            notification_email=request.notification_email
        )
    
    return TrackItemResponse(
        success=True,
        tracking_id=tracked_item.id,
        item_id=result.item_id,
        store=result.store,
        message=f"Now tracking item: {result.metadata.title if result.metadata else result.item_id}"
    )


@router.get("/history/{store}/{item_id}", response_model=PriceHistoryResponse)
async def get_price_history(
    store: str = Path(..., examples=["ebay"], description="스토어 타입"),
    item_id: str = Path(..., examples=["256123456789"], description="상품 ID"),
    days: int = Query(default=30, ge=1, le=365, description="조회할 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """
    상품의 가격 히스토리를 조회합니다.
    
    통계 정보와 함께 과거 가격 데이터를 반환합니다.
    
    **파라미터:**
    - `store`: 스토어 타입 (예: "ebay")
    - `item_id`: 상품 ID
    - `days`: 조회할 기간 (1-365일, 기본값: 30일)
    
    **응답 예시:**
    ```json
    {
        "store": "ebay",
        "item_id": "256123456789",
        "title": "Apple iPhone 14 Pro 256GB",
        "current_price": {
            "price": 999.99,
            "shipping_fee": 12.00,
            "currency": "USD"
        },
        "lowest_price": {
            "price": 899.99,
            "shipping_fee": 12.00,
            "currency": "USD"
        },
        "highest_price": {
            "price": 1099.99,
            "shipping_fee": 12.00,
            "currency": "USD"
        },
        "average_price": 989.50,
        "price_change_24h": -10.00,
        "price_change_percentage_24h": -0.99,
        "total_records": 45
    }
    ```
    """
    try:
        store_type = StoreType(store.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid store: {store}. Supported: ebay"
        )
    
    history_service = PriceHistoryService(db)
    return await history_service.get_price_history(
        store=store_type,
        item_id=item_id,
        days=days
    )


@router.get("/item/{store}/{item_id}")
async def get_item_details(
    store: str = Path(..., examples=["ebay"], description="스토어 타입"),
    item_id: str = Path(..., examples=["256123456789"], description="상품 ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    추적 중인 상품의 현재 상세 정보를 조회합니다.
    
    **파라미터:**
    - `store`: 스토어 타입 (예: "ebay")
    - `item_id`: 상품 ID
    
    **응답 예시:**
    ```json
    {
        "store": "ebay",
        "item_id": "256123456789",
        "title": "Apple iPhone 14 Pro 256GB",
        "condition": "new",
        "seller": "tech_seller",
        "price": {
            "amount": 999.99,
            "shipping": 12.00,
            "total": 1011.99,
            "currency": "USD"
        },
        "listing_type": "buy_it_now",
        "collected_at": "2024-01-30T12:00:00Z"
    }
    ```
    """
    try:
        store_type = StoreType(store.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid store: {store}"
        )
    
    # Get collector
    collector = CollectorRegistry.get_collector(store_type)
    if not collector:
        raise HTTPException(
            status_code=400,
            detail=f"No collector available for store: {store}"
        )
    
    # Build identifier
    from app.models.schemas import EbayIdentifier
    identifier = EbayIdentifier(item_id=item_id)
    
    # Collect current price
    result = await collector.collect_price(identifier)
    
    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error_message
        )
    
    return {
        "store": result.store.value,
        "item_id": result.item_id,
        "title": result.metadata.title if result.metadata else None,
        "condition": result.metadata.condition.value if result.metadata else None,
        "seller": result.metadata.seller_name if result.metadata else None,
        "price": {
            "amount": float(result.price_data.price),
            "shipping": float(result.price_data.shipping_fee),
            "total": float(result.price_data.total_price),
            "currency": result.price_data.currency
        } if result.price_data else None,
        "listing_type": result.metadata.listing_type.value if result.metadata else None,
        "bid_count": result.bid_count,
        "auction_end_time": result.auction_end_time.isoformat() if result.auction_end_time else None,
        "image_url": str(result.metadata.image_url) if result.metadata and result.metadata.image_url else None,
        "collected_at": result.collected_at.isoformat()
    }
