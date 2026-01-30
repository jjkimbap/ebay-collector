"""
eBay HTML scraper for fallback price collection.
Used when API is unavailable or returns incomplete data.
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.schemas import (
    CollectionMethod,
    CollectionResult,
    ItemCondition,
    ItemMetadata,
    ListingType,
    NormalizedPrice,
    PriceData,
    StoreType,
)


class EbayScraperError(Exception):
    """Custom exception for scraping errors."""
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(message)


class EbayScraper:
    """
    HTML scraper for eBay product pages.
    
    Fallback method when API is unavailable.
    Note: Use responsibly and respect eBay's terms of service.
    """
    
    # Request headers to mimic browser
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    # Price extraction patterns (updated based on actual eBay pages)
    PRICE_PATTERNS = [
        r'US\s*\$\s*([\d,]+\.?\d*)',  # US $636.58
        r'\$\s*([\d,]+\.?\d*)',        # $636.58
        r'USD\s*([\d,]+\.?\d*)',       # USD 636.58
        r'£\s*([\d,]+\.?\d*)',         # £500.00
        r'€\s*([\d,]+\.?\d*)',         # €500.00
    ]
    
    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=self.HEADERS
            )
        return self._http_client
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def fetch_page(self, url: str) -> str:
        """
        Fetch eBay product page HTML.
        
        Args:
            url: Product page URL
            
        Returns:
            Page HTML content
        """
        client = await self._get_http_client()
        response = await client.get(url)
        
        if response.status_code == 404:
            raise EbayScraperError("Item not found", code="ITEM_NOT_FOUND")
        
        if response.status_code != 200:
            raise EbayScraperError(
                f"Failed to fetch page: HTTP {response.status_code}",
                code="FETCH_ERROR"
            )
        
        return response.text
    
    def _extract_price(self, soup: BeautifulSoup) -> tuple[Optional[Decimal], str]:
        """Extract price from page."""
        currency = "USD"
        price = None
        
        # eBay 2024 페이지 구조 기반 선택자들
        # 1. 가격 텍스트를 포함하는 모든 요소에서 패턴 매칭 시도
        page_text = soup.get_text()
        
        # "US $XXX.XX" 패턴 찾기 (메인 가격)
        import re
        price_match = re.search(r'US\s*\$\s*([\d,]+\.\d{2})', page_text)
        if price_match:
            try:
                price_str = price_match.group(1).replace(',', '')
                price = Decimal(price_str)
                currency = "USD"
                return price, currency
            except:
                pass
        
        # 다양한 CSS 선택자 시도
        price_selectors = [
            # 2024년 eBay 구조
            'div[data-testid="x-price-primary"] span',
            'div[data-testid="x-bin-price"] span',
            'span.x-price-primary',
            'div.x-price-primary span',
            # 레거시 구조
            'span[itemprop="price"]',
            '#prcIsum',
            '#mm-saleDscPrc',
            'span.notranslate',  # 가격 표시용
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                price, currency = self._parse_price_text(text)
                if price is not None and price > 0:
                    return price, currency
        
        # meta 태그에서 가격 추출 시도
        price_meta = soup.select_one('meta[itemprop="price"]')
        if price_meta:
            try:
                price = Decimal(price_meta.get("content", "0"))
                currency_meta = soup.select_one('meta[itemprop="priceCurrency"]')
                if currency_meta:
                    currency = currency_meta.get("content", "USD")
                return price, currency
            except (InvalidOperation, ValueError):
                pass
        
        return price, currency
    
    def _parse_price_text(self, text: str) -> tuple[Optional[Decimal], str]:
        """Parse price from text string."""
        currency = "USD"
        
        # Detect currency
        if "£" in text or "GBP" in text:
            currency = "GBP"
        elif "€" in text or "EUR" in text:
            currency = "EUR"
        elif "C$" in text or "CAD" in text:
            currency = "CAD"
        elif "AU$" in text or "AUD" in text:
            currency = "AUD"
        
        # Extract numeric value
        # Remove currency symbols and parse
        cleaned = re.sub(r'[^\d.,]', '', text)
        
        # Handle comma as thousands separator
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Could be decimal separator (European) or thousands
            parts = cleaned.split(',')
            if len(parts[-1]) == 2:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        
        try:
            return Decimal(cleaned), currency
        except (InvalidOperation, ValueError):
            return None, currency
    
    def _extract_shipping(self, soup: BeautifulSoup) -> tuple[Decimal, bool]:
        """Extract shipping cost."""
        shipping_fee = Decimal("0.00")
        free_shipping = False
        
        # 페이지 텍스트에서 무료 배송 확인
        page_text = soup.get_text().lower()
        if "free shipping" in page_text or "free 2-3 day" in page_text or "free delivery" in page_text:
            return Decimal("0.00"), True
        
        # 배송비 선택자들
        shipping_selectors = [
            'div[data-testid="x-shipping-primary"] span',
            'span.ux-labels-values--shipping span.ux-textspans--BOLD',
            'span[id*="shippingCost"]',
            '#fshippingCost',
            'div.vim-fulfillment-pane span.ux-textspans',
        ]
        
        for selector in shipping_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True).lower()
                
                if "free" in text:
                    free_shipping = True
                    return Decimal("0.00"), True
                
                price, _ = self._parse_price_text(text)
                if price is not None and price > 0:
                    return price, False
        
        return shipping_fee, free_shipping
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract item title."""
        # 2024 eBay 구조 기반 선택자들
        title_selectors = [
            'h1.x-item-title__mainTitle span.ux-textspans',
            'h1.x-item-title__mainTitle',
            'h1[itemprop="name"]',
            'h1.product-title',
            '#itemTitle',
            'title',  # 페이지 타이틀에서 추출
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                # 페이지 타이틀인 경우 " | eBay" 제거
                if selector == 'title':
                    title = title.replace(' | eBay', '').strip()
                # "Details about" 접두어 제거
                title = re.sub(r'^Details about\s*', '', title, flags=re.IGNORECASE)
                if title and len(title) > 5:  # 유효한 타이틀인지 확인
                    return title
        
        return "Unknown Item"
    
    def _extract_seller(self, soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        """Extract seller information."""
        seller_id = None
        seller_name = None
        
        # 2024 eBay 구조: /str/sellername 형태의 링크 찾기
        seller_links = soup.select('a[href*="/str/"]')
        for link in seller_links:
            href = link.get("href", "")
            if "/str/" in href:
                # /str/directauth 형태에서 seller ID 추출
                parts = href.split("/str/")
                if len(parts) > 1:
                    seller_id = parts[1].split("?")[0].split("/")[0]
                    seller_name = link.get_text(strip=True) or seller_id
                    if seller_name and len(seller_name) > 1:
                        return seller_id, seller_name
        
        # 대체 선택자들
        seller_selectors = [
            'a.ux-seller-section__item--link',
            'a[data-testid="x-sellercard-atf__info__about-seller"]',
            'span.ux-seller-section__item--seller',
        ]
        
        for selector in seller_selectors:
            element = soup.select_one(selector)
            if element:
                seller_name = element.get_text(strip=True)
                href = element.get("href", "")
                if "/usr/" in href:
                    seller_id = href.split("/usr/")[-1].split("?")[0]
                elif "/str/" in href:
                    seller_id = href.split("/str/")[-1].split("?")[0]
                if seller_name:
                    return seller_id, seller_name
        
        return seller_id, seller_name
    
    def _extract_condition(self, soup: BeautifulSoup) -> ItemCondition:
        """Extract item condition."""
        # Item specifics 섹션에서 Condition 찾기
        page_text = soup.get_text().lower()
        
        # 직접 패턴 매칭
        if "brand new" in page_text or "condition: new" in page_text:
            return ItemCondition.NEW
        if "refurbished" in page_text:
            return ItemCondition.REFURBISHED
        if "pre-owned" in page_text or "used" in page_text:
            return ItemCondition.USED
        if "for parts" in page_text:
            return ItemCondition.FOR_PARTS
        
        # 선택자 기반 추출
        condition_selectors = [
            'div[data-testid="x-item-condition"] span',
            'span.ux-labels-values--condition span.ux-textspans',
            'div.x-item-condition span',
            '#vi-itm-cond',
        ]
        
        for selector in condition_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True).lower()
                
                if "new" in text and "like" not in text and "renew" not in text:
                    return ItemCondition.NEW
                elif "refurbished" in text or "like new" in text or "renewed" in text:
                    return ItemCondition.REFURBISHED
                elif "used" in text or "pre-owned" in text or "very good" in text or "good" in text:
                    return ItemCondition.USED
                elif "parts" in text:
                    return ItemCondition.FOR_PARTS
        
        return ItemCondition.UNKNOWN
    
    def _extract_listing_type(self, soup: BeautifulSoup) -> ListingType:
        """Extract listing type (auction vs buy it now)."""
        # Check for bid count
        bid_element = soup.select_one('span[id*="bidCount"], span.vi-VR-bid-count')
        if bid_element:
            # Check if also has buy it now
            bin_element = soup.select_one('span.x-buybox__cta-text')
            if bin_element and "buy it now" in bin_element.get_text(strip=True).lower():
                return ListingType.AUCTION_WITH_BIN
            return ListingType.AUCTION
        
        return ListingType.BUY_IT_NOW
    
    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main product image."""
        image_selectors = [
            'div.ux-image-carousel-item img',
            'img[itemprop="image"]',
            '#icImg',
        ]
        
        for selector in image_selectors:
            element = soup.select_one(selector)
            if element:
                # Try src, then data-src
                src = element.get("src") or element.get("data-src")
                if src and not src.startswith("data:"):
                    return src
        
        return None
    
    def _extract_auction_info(self, soup: BeautifulSoup) -> tuple[Optional[int], Optional[datetime]]:
        """Extract auction-specific information."""
        bid_count = None
        end_time = None
        
        # Bid count
        bid_element = soup.select_one('span[id*="bidCount"]')
        if bid_element:
            text = bid_element.get_text(strip=True)
            match = re.search(r'(\d+)', text)
            if match:
                bid_count = int(match.group(1))
        
        # End time - typically in a timer or countdown
        time_element = soup.select_one('span.ux-timer__text')
        if time_element:
            # This would need more complex parsing based on eBay's format
            pass
        
        return bid_count, end_time
    
    def parse_page(self, html: str, item_id: str) -> CollectionResult:
        """
        Parse eBay product page HTML.
        
        Args:
            html: Page HTML content
            item_id: eBay item ID
            
        Returns:
            CollectionResult with parsed data
        """
        try:
            soup = BeautifulSoup(html, "lxml")
            
            # Check if item is unavailable
            unavailable = soup.select_one('div.error__title, span.vi-err')
            if unavailable and "no longer available" in unavailable.get_text(strip=True).lower():
                return CollectionResult(
                    success=False,
                    store=StoreType.EBAY,
                    item_id=item_id,
                    error_code="ITEM_UNAVAILABLE",
                    error_message="This listing has ended or is no longer available",
                    collection_method=CollectionMethod.SCRAPING
                )
            
            # Extract price
            price, currency = self._extract_price(soup)
            if price is None:
                return CollectionResult(
                    success=False,
                    store=StoreType.EBAY,
                    item_id=item_id,
                    error_code="PRICE_NOT_FOUND",
                    error_message="Could not extract price from page",
                    collection_method=CollectionMethod.SCRAPING
                )
            
            # Extract other data
            shipping_fee, free_shipping = self._extract_shipping(soup)
            title = self._extract_title(soup)
            seller_id, seller_name = self._extract_seller(soup)
            condition = self._extract_condition(soup)
            listing_type = self._extract_listing_type(soup)
            image_url = self._extract_image(soup)
            bid_count, auction_end_time = self._extract_auction_info(soup)
            
            # Build price data
            price_data = PriceData(
                price=price,
                shipping_fee=shipping_fee,
                currency=currency
            )
            
            # Build normalized price
            normalized = NormalizedPrice(
                normalized_price=price,
                normalized_total=price + shipping_fee,
                currency=currency,
                includes_shipping=free_shipping,
                includes_tax=False
            )
            
            # Build metadata
            metadata = ItemMetadata(
                title=title,
                seller_id=seller_id,
                seller_name=seller_name,
                condition=condition,
                listing_type=listing_type,
                image_url=image_url
            )
            
            return CollectionResult(
                success=True,
                store=StoreType.EBAY,
                item_id=item_id,
                metadata=metadata,
                price_data=price_data,
                normalized_price=normalized,
                bid_count=bid_count,
                auction_end_time=auction_end_time,
                collection_method=CollectionMethod.SCRAPING
            )
            
        except Exception as e:
            return CollectionResult(
                success=False,
                store=StoreType.EBAY,
                item_id=item_id,
                error_code="PARSE_ERROR",
                error_message=str(e),
                collection_method=CollectionMethod.SCRAPING
            )
    
    async def collect_price(self, item_id: str, region: str = "US") -> CollectionResult:
        """
        Collect price by scraping eBay product page.
        
        Args:
            item_id: eBay item ID
            region: Region code for URL
            
        Returns:
            CollectionResult with price data
        """
        from app.collectors.ebay.url_parser import EbayUrlParser
        
        try:
            url = EbayUrlParser.build_canonical_url(item_id, region)
            html = await self.fetch_page(url)
            return self.parse_page(html, item_id)
        except EbayScraperError as e:
            return CollectionResult(
                success=False,
                store=StoreType.EBAY,
                item_id=item_id,
                error_code=e.code,
                error_message=e.message,
                collection_method=CollectionMethod.SCRAPING
            )
        except Exception as e:
            return CollectionResult(
                success=False,
                store=StoreType.EBAY,
                item_id=item_id,
                error_code="UNKNOWN_ERROR",
                error_message=str(e),
                collection_method=CollectionMethod.SCRAPING
            )
