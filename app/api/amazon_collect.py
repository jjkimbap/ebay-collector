"""
Amazon 상품 검색 API
"""
from typing import Any, Optional

import httpx
import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(prefix="/api/amazon/item_summary/search", tags=["amazon"])


class SearchItemResponse(BaseModel):
    """검색 결과 개별 아이템"""
    model_config = ConfigDict(extra="allow")  # 추가 필드 허용
    
    itemId: Optional[str] = None
    title: Optional[str] = None
    price: Optional[dict[str, Any]] = None
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
    Amazon 상품 검색 API
    
    Amazon Product Advertising API를 사용하여 상품을 검색합니다.
    
    **설정:**
    - API URL: `amazon_api_url` (config에서 설정)
    - Access Key: `amazon_access_key` (config에서 설정)
    - Secret Key: `amazon_secret_key` (config에서 설정)
    - Associate Tag: `amazon_associate_tag` (config에서 설정)
    """
    logger.info("Amazon search request", query=keyword, limit=limit)
    
    # Get API configuration from settings
    api_url = getattr(settings, "amazon_api_url", "https://webservices.amazon.com/paapi5/searchitems")
    access_key = getattr(settings, "amazon_access_key", "")
    secret_key = getattr(settings, "amazon_secret_key", "")
    associate_tag = getattr(settings, "amazon_associate_tag", "")
    
    if not access_key or not secret_key:
        logger.error("Amazon API credentials not configured")
        return SearchResponse(
            success=False,
            error="Amazon API credentials not configured. Please set AMAZON_ACCESS_KEY and AMAZON_SECRET_KEY in .env file."
        )
    
    # Prepare request
    params = {
        "Keywords": keyword,
        "ItemCount": limit,
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
    }
    
    # Note: Amazon API requires signature authentication
    # This is a simplified version - actual implementation should use AWS Signature Version 4
    logger.info(
        "Making Amazon API request",
        url=api_url,
        params=params,
        headers_keys=list(headers.keys())
    )
    
    # Make API request
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                api_url,
                json={
                    "Keywords": keyword,
                    "ItemCount": limit,
                    "PartnerTag": associate_tag,
                    "PartnerType": "Associates",
                    "Resources": [
                        "ItemInfo.Title",
                        "Offers.Listings.Price",
                        "Images.Primary.Large",
                        "ItemInfo.ByLineInfo",
                    ]
                },
                headers=headers,
            )
            
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = str(error_json)
                except:
                    pass
                
                logger.error(
                    "Amazon API request failed",
                    status_code=response.status_code,
                    response_text=error_detail[:1000],
                    request_url=api_url
                )
                return SearchResponse(
                    success=False,
                    error=f"API request failed: HTTP {response.status_code} - {error_detail[:500]}"
                )
            
            # Parse response
            data = response.json()
            
            # Transform response to match our schema
            item_summaries = []
            # Adjust based on actual Amazon API response structure
            if "SearchResult" in data and "Items" in data["SearchResult"]:
                for item in data["SearchResult"]["Items"]:
                    item_summaries.append(SearchItemResponse(**item))
            
            return SearchResponse(
                success=True,
                total=data.get("SearchResult", {}).get("TotalResultCount", len(item_summaries)),
                itemSummaries=item_summaries if item_summaries else None,
            )
            
        except httpx.TimeoutException:
            logger.error("Request timeout")
            return SearchResponse(
                success=False,
                error="Request timeout"
            )
        except httpx.RequestError as e:
            logger.error("Request error", error=str(e))
            return SearchResponse(
                success=False,
                error=f"Request error: {str(e)}"
            )
        except Exception as e:
            logger.error("Unexpected error", error=str(e), exc_info=True)
            return SearchResponse(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )

