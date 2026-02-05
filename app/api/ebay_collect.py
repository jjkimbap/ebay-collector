"""
eBay 상품 검색 API
"""
from typing import Any, Optional

import httpx
import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(prefix="/api/ebay/item_summary/search", tags=["ebay"])


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
    keyword: str = Query(..., description="검색 키워드 (예: 'drone', '3ce', 'iphone')"),
    limit: int = Query(3, ge=1, le=200, description="결과 수 (최대 200)"),
):
    """
    eBay 상품 검색 API
    
    eBay Browse API의 search 엔드포인트를 직접 호출합니다.
    OAuth 2.0 토큰을 사용하여 인증합니다.
    
    **엔드포인트:**
    `https://api.ebay.com/buy/browse/v1/item_summary/search`

    **응답:**
    eBay API의 원본 응답을 그대로 반환합니다.
    """
    from pathlib import Path
    
    logger.info("eBay search request", query=keyword, limit=limit)
    
    # Read OAuth token from file
    # Path: project_root/token
    token_file = Path(__file__).parent.parent.parent / "token"
    
    logger.debug("Token file path", path=str(token_file.resolve()))
    
    if not token_file.exists():
        logger.error("Token file not found", path=str(token_file.resolve()))
        return SearchResponse(
            success=False,
            error=f"Token file not found: {token_file.resolve()}"
        )
    
    try:
        # Read token file - try multiple encodings
        raw_content = None
        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                raw_content = token_file.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if raw_content is None:
            # Fallback to bytes
            raw_content = token_file.read_bytes().decode("utf-8", errors="ignore")
        
        logger.info("Token file read", content_length=len(raw_content), first_chars=raw_content[:50] if raw_content else None)
        
        # Strip whitespace and newlines
        token = raw_content.strip().strip('"').strip("'")
        
        # Remove any trailing newlines or carriage returns
        token = token.replace("\r", "").replace("\n", "").strip()
        
        if not token:
            logger.error(
                "Token file is empty",
                path=str(token_file.resolve()),
                file_size=token_file.stat().st_size if token_file.exists() else 0,
                raw_content_length=len(raw_content)
            )
            return SearchResponse(
                success=False,
                error=f"Token file is empty (file size: {token_file.stat().st_size if token_file.exists() else 0} bytes)"
            )
        
        # Validate token format (eBay tokens typically start with 'v^')
        if not token.startswith("v^"):
            logger.warning("Token format may be invalid", token_prefix=token[:30])
        
        logger.info("Token loaded successfully", token_length=len(token), token_prefix=token[:30] + "..." if len(token) > 30 else token)
    except FileNotFoundError:
        logger.error("Token file not found", path=str(token_file.resolve()))
        return SearchResponse(
            success=False,
            error=f"Token file not found: {token_file.resolve()}"
        )
    except Exception as e:
        logger.error("Failed to read token file", error=str(e), exc_info=True)
        return SearchResponse(
            success=False,
            error=f"Failed to read token file: {str(e)}"
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
        "X-EBAY-C-MARKETPLACE-ID": getattr(settings, "ebay_marketplace_id", "EBAY_US"),
        "X-EBAY-C-ENDUSERCTX": getattr(settings, "ebay_enduserctx", "affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>"),
        "Content-Type": "application/json",
    }
    
    # Log request details for debugging (without exposing full token)
    logger.info(
        "Making eBay API request",
        url=api_url,
        params=params,
        headers_keys=list(headers.keys()),
        token_length=len(token),
        token_starts_with=token[:50] if len(token) > 50 else token,
        token_format_valid=token.startswith("v^"),
        marketplace_id=headers["X-EBAY-C-MARKETPLACE-ID"],
        enduserctx=headers["X-EBAY-C-ENDUSERCTX"]
    )
    
    # Make API request
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                api_url,
                params=params,
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
                    "eBay API request failed",
                    status_code=response.status_code,
                    response_text=error_detail[:1000],
                    request_url=api_url,
                    request_params=params,
                    token_length=len(token),
                    token_prefix=token[:30] if len(token) > 30 else token
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

