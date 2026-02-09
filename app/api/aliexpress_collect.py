"""
AliExpress Affiliates API 상품 검색
"""
import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any, Optional

import httpx
import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/aliexpress/item_summary/search", tags=["aliexpress"])


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
    category: Optional[str] = None  # 카테고리
    image: Optional[dict[str, Any]] = None
    itemWebUrl: Optional[str] = None
    commissionRate: Optional[str] = None  # 커미션율 (Affiliates API)


class SearchResponse(BaseModel):
    """검색 응답 모델"""
    success: bool
    total: Optional[int] = None
    itemSummaries: Optional[list[SearchItemResponse]] = None
    error: Optional[str] = None


class AliExpressAffiliateClient:
    """AliExpress Affiliates API 클라이언트"""
    
    def __init__(self, url: str, app_key: str, app_secret: str):
        self.url = url.rstrip('/')
        self.app_key = app_key
        self.app_secret = app_secret
    
    def _generate_signature(self, params: dict[str, str]) -> str:
        """HMAC-SHA256 서명 생성"""
        # 파라미터를 정렬하고 URL 인코딩
        sorted_params = sorted(params.items())
        query_string = '&'.join([f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params])
        
        # 서명 생성
        sign_string = f"{self.app_secret}&{query_string}&{self.app_secret}"
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        
        return signature
    
    def execute(self, api_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """API 요청 실행"""
        # 기본 파라미터 설정
        request_params: dict[str, str] = {
            'method': api_name,
            'app_key': self.app_key,
            'timestamp': str(int(time.time() * 1000)),  # 밀리초 타임스탬프
            'format': 'json',
            'v': '2.0',
            'sign_method': 'sha256',
        }
        
        # 사용자 파라미터 추가
        for key, value in params.items():
            if value is not None:
                request_params[key] = str(value)
        
        # 서명 생성 및 추가
        signature = self._generate_signature(request_params)
        request_params['sign'] = signature
        
        # HTTP 요청
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.url,
                    data=request_params,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error("AliExpress Affiliates API request failed", error=str(e))
            raise


def _normalize_price(price_str: Optional[str], currency: Optional[str] = None) -> Optional[dict[str, Any]]:
    """가격 문자열을 정규화"""
    if not price_str:
        return None
    
    try:
        # 숫자만 추출
        import re
        price_match = re.search(r'([\d,]+\.?\d*)', str(price_str).replace(',', ''))
        if price_match:
            value = price_match.group(1)
            return {
                "value": value,
                "currency": currency or "USD"
            }
    except Exception:
        pass
    
    return None


def _transform_affiliate_response(api_response: dict[str, Any], limit: int) -> dict[str, Any]:
    """Affiliates API 응답을 표준 형식으로 변환"""
    try:
        # 응답 구조 확인 (API 응답 형식에 따라 조정 필요)
        if 'aliexpress_affiliate_product_query_response' in api_response:
            response_data = api_response['aliexpress_affiliate_product_query_response']
        elif 'response' in api_response:
            response_data = api_response['response']
        else:
            response_data = api_response
        
        # 에러 확인
        if 'error_response' in api_response:
            error = api_response['error_response']
            error_msg = error.get('msg', 'Unknown error')
            error_code = error.get('code', '')
            return {
                "success": False,
                "error": f"AliExpress API Error [{error_code}]: {error_msg}"
            }
        
        # 상품 목록 추출
        products = []
        if 'result' in response_data:
            result = response_data['result']
            if 'products' in result:
                products = result['products'].get('product', [])
            elif 'product' in result:
                products = result['product'] if isinstance(result['product'], list) else [result['product']]
        
        # 상품 데이터 변환
        items = []
        for product in products[:limit]:
            # 가격 정보
            sale_price = product.get('sale_price', '')
            original_price = product.get('original_price', '') or sale_price
            currency = product.get('target_currency', 'USD')
            
            # 할인율 계산
            discount = None
            if original_price and sale_price:
                try:
                    orig = float(str(original_price).replace(',', ''))
                    sale = float(str(sale_price).replace(',', ''))
                    if orig > sale and orig > 0:
                        discount_pct = int(((orig - sale) / orig) * 100)
                        discount = f"{discount_pct}%"
                except Exception:
                    pass
            
            item = {
                "itemId": product.get('product_id') or product.get('productId'),
                "title": product.get('product_title') or product.get('title'),
                "price": _normalize_price(sale_price, currency),
                "originalPrice": _normalize_price(original_price, currency),
                "discount": discount,
                "rating": product.get('evaluate_rate') or product.get('rating'),
                "sales": product.get('volume') or product.get('sales'),
                "condition": None,
                "category": product.get('category_name') or product.get('category'),
                "image": {
                    "imageUrl": product.get('product_main_image_url') or product.get('image_url')
                } if product.get('product_main_image_url') or product.get('image_url') else None,
                "itemWebUrl": product.get('promotion_link') or product.get('product_url'),
                "commissionRate": product.get('commission_rate') or product.get('commissionRate'),
            }
            items.append(item)
        
        total = response_data.get('total_results', len(items)) if 'total_results' in response_data else len(items)
        
        return {
            "success": True,
            "total": total,
            "items": items
        }
    
    except Exception as e:
        logger.error("Failed to transform AliExpress Affiliates API response", error=str(e), response=api_response)
        return {
            "success": False,
            "error": f"Failed to parse API response: {str(e)}"
        }


@router.get("", response_model=SearchResponse)
async def search_products(
    keyword: str = Query(..., description="검색 키워드"),
    limit: int = Query(3, ge=1, le=200, description="결과 수 (최대 200)"),
    category_ids: Optional[str] = Query(None, description="카테고리 ID (쉼표로 구분)"),
    min_price: Optional[float] = Query(None, description="최소 가격"),
    max_price: Optional[float] = Query(None, description="최대 가격"),
    target_currency: str = Query("USD", description="통화 (USD, KRW 등)"),
    target_language: str = Query("EN", description="언어 (EN, KO 등)"),
    sort: str = Query("SALE_PRICE_ASC", description="정렬 방식 (SALE_PRICE_ASC, SALE_PRICE_DESC 등)"),
    tracking_id: Optional[str] = Query(None, description="트래킹 ID"),
    ship_to_country: Optional[str] = Query(None, description="배송 국가 코드 (US, KR 등)"),
):
    """
    AliExpress Affiliates API를 사용한 상품 검색
    
    **필수 설정 (.env):**
    - ALI_AFFILIATE_API_URL: API 엔드포인트 URL
    - ALI_AFFILIATE_APP_KEY: App Key
    - ALI_AFFILIATE_APP_SECRET: App Secret
    
    **수집 정보:**
    - 상품 제목, 가격, 원래 가격, 할인율
    - 평점, 판매량
    - 카테고리
    - 상품 이미지, 링크
    - 커미션율 (Affiliates API 전용)
    """
    settings = get_settings()
    
    # 설정 확인
    api_url = getattr(settings, 'ali_affiliate_api_url', '') or 'https://api-sg.aliexpress.com/sync'
    app_key = getattr(settings, 'ali_affiliate_app_key', '') or settings.ali_api_key
    app_secret = getattr(settings, 'ali_affiliate_app_secret', '') or ''
    
    if not app_key or not app_secret:
        logger.error("AliExpress Affiliates API credentials not configured")
        return SearchResponse(
            success=False,
            error="AliExpress Affiliates API credentials not configured. Please set ALI_AFFILIATE_APP_KEY and ALI_AFFILIATE_APP_SECRET"
        )
    
    logger.info("AliExpress Affiliates API search request", query=keyword, limit=limit)
    
    try:
        # API 클라이언트 생성
        client = AliExpressAffiliateClient(api_url, app_key, app_secret)
        
        # API 파라미터 구성
        api_params: dict[str, Any] = {
            'keywords': keyword,
            'page_no': '1',
            'page_size': str(min(limit, 50)),  # API 제한 확인 필요
            'target_currency': target_currency,
            'target_language': target_language,
            'sort': sort,
            'platform_product_type': 'ALL',
        }
        
        # 선택적 파라미터 추가
        if category_ids:
            api_params['category_ids'] = category_ids
        if min_price is not None:
            api_params['min_sale_price'] = str(min_price)
        if max_price is not None:
            api_params['max_sale_price'] = str(max_price)
        if tracking_id:
            api_params['tracking_id'] = tracking_id
        if ship_to_country:
            api_params['ship_to_country'] = ship_to_country
        
        # 필드 지정 (필요한 정보만 요청)
        api_params['fields'] = 'commission_rate,sale_price,original_price,product_title,product_id,product_main_image_url,promotion_link,evaluate_rate,volume,category_name'
        
        # API 호출
        response = client.execute('aliexpress.affiliate.product.query', api_params)
        
        # 응답 변환
        result = _transform_affiliate_response(response, limit)
        
        if not result.get("success"):
            return SearchResponse(success=False, error=result.get("error", "Unknown error"))
        
        item_summaries = [SearchItemResponse(**item) for item in result.get("items", [])]
        return SearchResponse(
            success=True,
            total=result.get("total", len(item_summaries)),
            itemSummaries=item_summaries if item_summaries else None,
        )
    
    except Exception as e:
        logger.error("AliExpress Affiliates API error", error=str(e), exc_info=True)
        return SearchResponse(
            success=False,
            error=f"AliExpress Affiliates API error: {str(e)}"
        )
