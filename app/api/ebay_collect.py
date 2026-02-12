"""
eBay 상품 검색 API
"""
from typing import Any, Optional

import httpx
import structlog
from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.lib.ebay_token_manager import EbayTokenManager

logger = structlog.get_logger()
settings = get_settings()

# 검색 API 라우터
search_router = APIRouter(prefix="/api/ebay/item_summary/search", tags=["ebay"])

# 상세 정보 API 라우터
item_router = APIRouter(prefix="/api/ebay/item", tags=["ebay"])

# 전역 토큰 관리자 인스턴스
_token_manager: Optional[EbayTokenManager] = None


def get_token_manager() -> EbayTokenManager:
    """토큰 관리자 싱글톤 인스턴스 반환"""
    global _token_manager
    
    if _token_manager is None:
        if not settings.ebay_app_id or not settings.ebay_cert_id:
            raise ValueError("eBay App ID and Cert ID must be configured in settings")
        
        _token_manager = EbayTokenManager(
            app_id=settings.ebay_app_id,
            cert_id=settings.ebay_cert_id
        )
        
        # 기존 토큰 파일이 있으면 로드 시도
        _token_manager.load_token_from_file()
    
    return _token_manager


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


@search_router.get("", response_model=SearchResponse)
async def search_products(
    keyword: str = Query(..., description="검색 키워드 (예: 'drone', '3ce', 'iphone')"),
    limit: int = Query(3, ge=1, le=200, description="결과 수 (최대 200)"),
):
    """
    eBay 상품 검색 API
    
    eBay Browse API의 search 엔드포인트를 직접 호출합니다.
    OAuth 2.0 토큰을 사용하여 인증합니다.
    
    **응답:**
    eBay API의 원본 응답을 그대로 반환합니다.
    """
    logger.info("eBay search request", query=keyword, limit=limit)
    
    # 토큰 관리자에서 토큰 가져오기
    try:
        token_manager = get_token_manager()
        token = token_manager.get_token()
    except ValueError as e:
        logger.error("Token manager initialization failed", error=str(e))
        return SearchResponse(
            success=False,
            error=f"Token manager error: {str(e)}"
        )
    except Exception as e:
        logger.error("Failed to get token", error=str(e), exc_info=True)
        return SearchResponse(
            success=False,
            error=f"Failed to get token: {str(e)}"
        )
    
    # eBay API endpoint - use config if available
    api_url = getattr(settings, "ebay_api_url", "https://api.ebay.com/buy/browse/v1/item_summary/search")
    
    # Prepare request
    params = {
        "q": keyword,
        "limit": limit,
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": getattr(settings, "ebay_marketplace_id", "EBAY_KR"),
        "X-EBAY-C-ENDUSERCTX": getattr(settings, "ebay_enduserctx", "affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>"),
        "Content-Type": "application/json",
    }
    
    # Make API request
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                api_url,
                params=params,
                headers=headers,
            )
            
            # 토큰 만료 에러(401) 발생 시 재발급 후 재시도
            if response.status_code == 401:
                logger.warning("Token expired, refreshing and retrying")
                try:
                    token_manager._refresh_token()
                    token = token_manager.get_token()
                    headers["Authorization"] = f"Bearer {token}"
                    
                    # 재시도
                    response = await client.get(
                        api_url,
                        params=params,
                        headers=headers,
                    )
                except Exception as retry_error:
                    logger.error("Failed to refresh token on 401 error", error=str(retry_error))
                    return SearchResponse(
                        success=False,
                        error=f"Token refresh failed: {str(retry_error)}"
                    )
            
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = str(error_json)
                except:
                    pass
                
                logger.error(
                    "eBay API request failed",
                    status_code=response.status_code,
                    response_text=error_detail[:1000],
                    request_url=api_url,
                    request_params=params,
                )
                return SearchResponse(
                    success=False,
                    error=f"API request failed: HTTP {response.status_code} - {error_detail[:500]}"
                )
            
            # Parse response
            data = response.json()
            
            # Transform response to match our schema
            item_summaries = []
            if "itemSummaries" in data:
                for item in data["itemSummaries"]:
                    item_summaries.append(SearchItemResponse(**item))
            
            return SearchResponse(
                success=True,
                total=data.get("total"),
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


class ItemDetailResponse(BaseModel):
    """상품 상세 정보 응답 모델"""
    success: bool
    item: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    model_config = ConfigDict(extra="allow")  # 추가 필드 허용


@item_router.get("/{item_id}", response_model=ItemDetailResponse)
async def get_item_detail(
    item_id: str = Path(..., description="eBay 아이템 ID (예: 'v1|285638069992|0')"),
):
    """
    eBay Item API를 사용한 상품 상세 정보 조회 API
    
    eBay API의 item 엔드포인트를 사용하여 특정 상품의 상세 정보를 가져옵니다.
    OAuth 2.0 토큰을 사용하여 인증합니다.
    
    """
    logger.info("eBay item detail request", item_id=item_id)
    
    # 토큰 관리자에서 토큰 가져오기
    try:
        token_manager = get_token_manager()
        token = token_manager.get_token()
    except ValueError as e:
        logger.error("Token manager initialization failed", error=str(e))
        return ItemDetailResponse(
            success=False,
            error=f"Token manager error: {str(e)}"
        )
    except Exception as e:
        logger.error("Failed to get token", error=str(e), exc_info=True)
        return ItemDetailResponse(
            success=False,
            error=f"Failed to get token: {str(e)}"
        )
    
    # eBay Item API endpoint
    item_api_url = getattr(settings, "ebay_item_api_url", "https://api.ebay.com/buy/browse/v1/item")
    url = f"{item_api_url}/{item_id}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": getattr(settings, "ebay_marketplace_id", "EBAY_KR"),
        "X-EBAY-C-ENDUSERCTX": getattr(settings, "ebay_enduserctx", "affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>"),
        "Content-Type": "application/json",
    }
    
    # Make API request
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            
            # 토큰 만료 에러(401) 발생 시 재발급 후 재시도
            if response.status_code == 401:
                logger.warning("Token expired, refreshing and retrying")
                try:
                    token_manager._refresh_token()
                    token = token_manager.get_token()
                    headers["Authorization"] = f"Bearer {token}"
                    
                    # 재시도
                    response = await client.get(url, headers=headers)
                except Exception as retry_error:
                    logger.error("Failed to refresh token on 401 error", error=str(retry_error))
                    return ItemDetailResponse(
                        success=False,
                        error=f"Token refresh failed: {str(retry_error)}"
                    )
            
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = str(error_json)
                except:
                    pass
                
                logger.error(
                    "eBay Item API request failed",
                    status_code=response.status_code,
                    response_text=error_detail[:1000],
                    request_url=url,
                    item_id=item_id,
                )
                return ItemDetailResponse(
                    success=False,
                    error=f"API request failed: HTTP {response.status_code} - {error_detail[:500]}"
                )
            
            # Parse response
            item_data = response.json()
            
            return ItemDetailResponse(
                success=True,
                item=item_data,
            )
            
        except httpx.TimeoutException:
            logger.error("Request timeout", item_id=item_id)
            return ItemDetailResponse(
                success=False,
                error="Request timeout"
            )
        except httpx.RequestError as e:
            logger.error("Request error", error=str(e), item_id=item_id)
            return ItemDetailResponse(
                success=False,
                error=f"Request error: {str(e)}"
            )
        except Exception as e:
            logger.error("Unexpected error", error=str(e), item_id=item_id, exc_info=True)
            return ItemDetailResponse(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )

