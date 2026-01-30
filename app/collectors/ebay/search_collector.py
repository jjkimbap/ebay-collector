"""
eBay 검색 결과 수집기 (Search Collector)

브랜드명이나 키워드로 검색하여 여러 상품의 가격 정보를 일괄 수집합니다.

사용 예시:
- 검색어: "3ce"
- 검색어: "3ce lipstick"
- 카테고리 + 검색어: "3ce" in "Makeup" category
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.ebay.api_client import EbayApiClient, EbayApiError
from app.core.config import get_settings
from app.models.schemas import (
    CollectionMethod,
    ItemCondition,
    ListingType,
    StoreType,
)


@dataclass
class SearchItem:
    """검색 결과의 개별 상품 정보"""
    item_id: str
    title: str
    price: Decimal
    currency: str
    shipping_fee: Decimal = Decimal("0.00")
    total_price: Decimal = Decimal("0.00")
    
    # 메타 정보
    condition: str = "unknown"
    listing_type: str = "buy_it_now"
    seller_id: Optional[str] = None
    seller_name: Optional[str] = None
    
    # 이미지 및 URL
    image_url: Optional[str] = None
    item_url: Optional[str] = None
    
    # 경매 정보
    bid_count: Optional[int] = None
    
    # 추가 정보
    category: Optional[str] = None
    location: Optional[str] = None
    
    def __post_init__(self):
        if self.total_price == Decimal("0.00"):
            self.total_price = self.price + self.shipping_fee


@dataclass
class SearchResult:
    """검색 결과 전체"""
    success: bool
    query: str
    total_count: int = 0
    items: list[SearchItem] = field(default_factory=list)
    
    # 페이지네이션
    page: int = 1
    page_size: int = 50
    has_more: bool = False
    
    # 메타 정보
    search_url: Optional[str] = None
    collected_at: datetime = field(default_factory=datetime.utcnow)
    collection_method: str = "api"
    
    # 에러 정보
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # 통계
    @property
    def price_stats(self) -> dict:
        """가격 통계 계산"""
        if not self.items:
            return {}
        
        prices = [item.total_price for item in self.items]
        return {
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices),
            "item_count": len(self.items)
        }


class EbaySearchCollector:
    """
    eBay 검색 기반 가격 수집기
    
    eBay Browse API의 search endpoint를 사용하여
    키워드/브랜드 기반으로 상품 목록과 가격을 수집합니다.
    """
    
    # eBay Browse API Search endpoint
    SANDBOX_SEARCH_URL = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
    PRODUCTION_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    
    # 카테고리 ID 매핑 (자주 사용되는 것들)
    CATEGORY_MAP = {
        "makeup": "31786",
        "cosmetics": "31786",
        "beauty": "26395",
        "skincare": "11863",
        "electronics": "293",
        "phones": "9355",
        "computers": "58058",
        "clothing": "11450",
        "shoes": "93427",
    }
    
    def __init__(self):
        self.settings = get_settings()
        self._api_client: Optional[EbayApiClient] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def api_client(self) -> EbayApiClient:
        if self._api_client is None:
            self._api_client = EbayApiClient()
        return self._api_client
    
    @property
    def search_url(self) -> str:
        if self.settings.ebay_sandbox_mode:
            return self.SANDBOX_SEARCH_URL
        return self.PRODUCTION_SEARCH_URL
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    async def close(self):
        """리소스 정리"""
        if self._api_client:
            await self._api_client.close()
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    def _build_search_params(
        self,
        query: str,
        category_id: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        condition: Optional[str] = None,
        sort: str = "price",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """검색 파라미터 구성"""
        params = {
            "q": query,
            "limit": min(limit, 200),  # eBay API 최대 200
            "offset": offset,
        }
        
        # 카테고리 필터
        if category_id:
            params["category_ids"] = category_id
        
        # 가격 필터
        filters = []
        if min_price is not None:
            filters.append(f"price:[{min_price}..{max_price or ''}]")
        elif max_price is not None:
            filters.append(f"price:[..{max_price}]")
        
        # 상태 필터
        if condition:
            condition_map = {
                "new": "NEW",
                "used": "USED",
                "refurbished": "REFURBISHED",
            }
            if condition.lower() in condition_map:
                filters.append(f"conditions:{{{condition_map[condition.lower()]}}}")
        
        if filters:
            params["filter"] = ",".join(filters)
        
        # 정렬
        sort_map = {
            "price": "price",
            "price_desc": "-price",
            "date": "newlyListed",
            "best_match": "bestMatch",
        }
        params["sort"] = sort_map.get(sort, "price")
        
        return params
    
    def _parse_search_item(self, item_data: dict) -> SearchItem:
        """API 응답에서 SearchItem 파싱"""
        # 가격 추출
        price_info = item_data.get("price", {})
        price = Decimal(str(price_info.get("value", "0")))
        currency = price_info.get("currency", "USD")
        
        # 배송비 추출
        shipping_options = item_data.get("shippingOptions", [])
        shipping_fee = Decimal("0.00")
        if shipping_options:
            shipping_cost = shipping_options[0].get("shippingCost", {})
            shipping_fee = Decimal(str(shipping_cost.get("value", "0")))
        
        # 상태 파싱
        condition = item_data.get("condition", "UNKNOWN").lower()
        
        # 판매자 정보
        seller_info = item_data.get("seller", {})
        
        # 이미지
        image_info = item_data.get("image", {}) or item_data.get("thumbnailImages", [{}])[0]
        image_url = image_info.get("imageUrl")
        
        # Listing 타입
        buying_options = item_data.get("buyingOptions", [])
        listing_type = "buy_it_now"
        if "AUCTION" in buying_options:
            listing_type = "auction"
        
        return SearchItem(
            item_id=item_data.get("legacyItemId", item_data.get("itemId", "")),
            title=item_data.get("title", "Unknown"),
            price=price,
            currency=currency,
            shipping_fee=shipping_fee,
            condition=condition,
            listing_type=listing_type,
            seller_id=seller_info.get("username"),
            seller_name=seller_info.get("username"),
            image_url=image_url,
            item_url=item_data.get("itemWebUrl"),
            bid_count=item_data.get("bidCount"),
            category=item_data.get("categoryPath"),
            location=item_data.get("itemLocation", {}).get("country"),
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        condition: Optional[str] = None,
        sort: str = "price",
        limit: int = 50,
        page: int = 1,
    ) -> SearchResult:
        """
        eBay 상품 검색
        
        Args:
            query: 검색 키워드 (예: "3ce", "3ce lipstick")
            category: 카테고리 이름 또는 ID (예: "makeup", "31786")
            min_price: 최소 가격
            max_price: 최대 가격
            condition: 상품 상태 (new, used, refurbished)
            sort: 정렬 방식 (price, price_desc, date, best_match)
            limit: 결과 수 (최대 200)
            page: 페이지 번호
            
        Returns:
            SearchResult with items list
        """
        # 카테고리 ID 변환
        category_id = None
        if category:
            category_id = self.CATEGORY_MAP.get(category.lower(), category)
        
        # API 토큰 확인
        if not self.settings.ebay_api_configured:
            return SearchResult(
                success=False,
                query=query,
                error_code="API_NOT_CONFIGURED",
                error_message="eBay API credentials not configured. Please set EBAY_APP_ID and EBAY_CERT_ID."
            )
        
        try:
            # 토큰 가져오기
            token = await self.api_client._ensure_token()
            
            # 파라미터 구성
            offset = (page - 1) * limit
            params = self._build_search_params(
                query=query,
                category_id=category_id,
                min_price=min_price,
                max_price=max_price,
                condition=condition,
                sort=sort,
                limit=limit,
                offset=offset,
            )
            
            # API 호출
            client = await self._get_http_client()
            response = await client.get(
                self.search_url,
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                    "Content-Type": "application/json",
                }
            )
            
            if response.status_code != 200:
                return SearchResult(
                    success=False,
                    query=query,
                    error_code="API_ERROR",
                    error_message=f"API returned status {response.status_code}: {response.text[:200]}"
                )
            
            data = response.json()
            
            # 결과 파싱
            items = []
            item_summaries = data.get("itemSummaries", [])
            for item_data in item_summaries:
                try:
                    item = self._parse_search_item(item_data)
                    items.append(item)
                except Exception as e:
                    # 개별 아이템 파싱 실패는 건너뛰기
                    continue
            
            total = data.get("total", len(items))
            has_more = offset + len(items) < total
            
            return SearchResult(
                success=True,
                query=query,
                total_count=total,
                items=items,
                page=page,
                page_size=limit,
                has_more=has_more,
                search_url=f"https://www.ebay.com/sch/i.html?_nkw={query}",
                collection_method="api",
            )
            
        except EbayApiError as e:
            return SearchResult(
                success=False,
                query=query,
                error_code=e.code,
                error_message=e.message
            )
        except Exception as e:
            return SearchResult(
                success=False,
                query=query,
                error_code="UNKNOWN_ERROR",
                error_message=str(e)
            )
    
    async def search_brand(
        self,
        brand: str,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> SearchResult:
        """
        브랜드명으로 검색
        
        Args:
            brand: 브랜드명 (예: "3ce", "MAC", "Dior")
            category: 카테고리 (예: "makeup", "skincare")
            limit: 결과 수
        """
        return await self.search(
            query=brand,
            category=category,
            limit=limit,
            sort="best_match"
        )
    
    async def collect_all_pages(
        self,
        query: str,
        max_items: int = 500,
        **kwargs
    ) -> SearchResult:
        """
        여러 페이지에 걸쳐 모든 결과 수집
        
        Args:
            query: 검색 키워드
            max_items: 최대 수집 아이템 수
            **kwargs: search() 에 전달할 추가 파라미터
        """
        all_items = []
        page = 1
        page_size = min(200, max_items)  # API 최대 200
        
        while len(all_items) < max_items:
            result = await self.search(
                query=query,
                limit=page_size,
                page=page,
                **kwargs
            )
            
            if not result.success:
                # 첫 페이지 실패면 에러 반환
                if page == 1:
                    return result
                break
            
            all_items.extend(result.items)
            
            if not result.has_more:
                break
            
            page += 1
        
        # 최대 개수로 자르기
        all_items = all_items[:max_items]
        
        return SearchResult(
            success=True,
            query=query,
            total_count=len(all_items),
            items=all_items,
            page=1,
            page_size=len(all_items),
            has_more=False,
            collection_method="api",
        )


# API 없이 사용할 수 있는 간단한 검색 결과 시뮬레이션 (테스트용)
def create_mock_search_result(query: str) -> SearchResult:
    """
    API 키 없이 테스트할 때 사용하는 모의 데이터
    
    실제로는 eBay API를 사용해야 합니다.
    """
    mock_items = [
        SearchItem(
            item_id="387049030112",
            title="3CE MAKEUP FIXER MIST 100ml, Setting Sprays, Korean Cosmetics",
            price=Decimal("15.99"),
            currency="USD",
            shipping_fee=Decimal("9.50"),
            condition="new",
            seller_name="kbeautybloom",
            image_url="https://i.ebayimg.com/images/g/example.jpg",
            item_url="https://www.ebay.com/itm/387049030112",
        ),
        SearchItem(
            item_id="387049030140",
            title="3CE WATER MAKE UP BASE SPF50+PA++++, Korean cosmetics",
            price=Decimal("18.99"),
            currency="USD",
            shipping_fee=Decimal("9.50"),
            condition="new",
            seller_name="kbeautybloom",
            image_url="https://i.ebayimg.com/images/g/example2.jpg",
            item_url="https://www.ebay.com/itm/387049030140",
        ),
        SearchItem(
            item_id="123456789012",
            title="3CE Velvet Lip Tint #TAUPE - Korean Makeup",
            price=Decimal("12.50"),
            currency="USD",
            shipping_fee=Decimal("5.00"),
            condition="new",
            seller_name="koreanbeauty_store",
            item_url="https://www.ebay.com/itm/123456789012",
        ),
    ]
    
    return SearchResult(
        success=True,
        query=query,
        total_count=len(mock_items),
        items=mock_items,
        collection_method="mock",
    )
