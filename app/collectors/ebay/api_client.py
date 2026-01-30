"""
eBay API client for Browse API.
Primary method for price collection.
"""
import base64
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
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


class EbayApiError(Exception):
    """Custom exception for eBay API errors."""
    def __init__(self, message: str, code: str = None, status_code: int = None):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class EbayApiClient:
    """
    Client for eBay Browse API.
    
    Handles OAuth authentication and item data retrieval.
    https://developer.ebay.com/api-docs/buy/browse/overview.html
    """
    
    # API endpoints
    SANDBOX_AUTH_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    PRODUCTION_AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    
    SANDBOX_API_URL = "https://api.sandbox.ebay.com/buy/browse/v1"
    PRODUCTION_API_URL = "https://api.ebay.com/buy/browse/v1"
    
    def __init__(self):
        self.settings = get_settings()
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def auth_url(self) -> str:
        if self.settings.ebay_sandbox_mode:
            return self.SANDBOX_AUTH_URL
        return self.PRODUCTION_AUTH_URL
    
    @property
    def api_url(self) -> str:
        if self.settings.ebay_sandbox_mode:
            return self.SANDBOX_API_URL
        return self.PRODUCTION_API_URL
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True
            )
        return self._http_client
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    def _get_basic_auth_header(self) -> str:
        """Generate Basic Auth header for OAuth."""
        credentials = f"{self.settings.ebay_app_id}:{self.settings.ebay_cert_id}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    async def _ensure_token(self) -> str:
        """Ensure we have a valid access token."""
        # Check if current token is still valid
        if (self._access_token and self._token_expires_at and 
            datetime.utcnow() < self._token_expires_at - timedelta(minutes=5)):
            return self._access_token
        
        # Get new token
        await self._refresh_token()
        return self._access_token
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _refresh_token(self) -> None:
        """Refresh OAuth access token."""
        if not self.settings.ebay_api_configured:
            raise EbayApiError(
                "eBay API credentials not configured",
                code="AUTH_NOT_CONFIGURED"
            )
        
        client = await self._get_http_client()
        
        response = await client.post(
            self.auth_url,
            headers={
                "Authorization": self._get_basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope"
            }
        )
        
        if response.status_code != 200:
            raise EbayApiError(
                f"Failed to get access token: {response.text}",
                code="AUTH_FAILED",
                status_code=response.status_code
            )
        
        data = response.json()
        self._access_token = data["access_token"]
        # Token typically expires in 2 hours
        expires_in = data.get("expires_in", 7200)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_item(self, item_id: str) -> dict[str, Any]:
        """
        Get item details from eBay Browse API.
        
        Args:
            item_id: eBay item ID
            
        Returns:
            Raw API response data
        """
        token = await self._ensure_token()
        client = await self._get_http_client()
        
        # Build legacy item ID format for v1 API
        # Format: v1|{itemId}|0
        legacy_id = f"v1|{item_id}|0"
        
        response = await client.get(
            f"{self.api_url}/item/{legacy_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "X-EBAY-C-ENDUSERCTX": "affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>"
            }
        )
        
        if response.status_code == 404:
            raise EbayApiError(
                f"Item not found: {item_id}",
                code="ITEM_NOT_FOUND",
                status_code=404
            )
        
        if response.status_code != 200:
            raise EbayApiError(
                f"API request failed: {response.text}",
                code="API_ERROR",
                status_code=response.status_code
            )
        
        return response.json()
    
    async def get_item_by_url(self, url: str) -> dict[str, Any]:
        """
        Get item details using item web URL.
        
        Uses the getItemByLegacyId endpoint.
        """
        token = await self._ensure_token()
        client = await self._get_http_client()
        
        response = await client.get(
            f"{self.api_url}/item/get_item_by_legacy_id",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
            },
            params={"legacy_item_id": url}
        )
        
        if response.status_code != 200:
            raise EbayApiError(
                f"API request failed: {response.text}",
                code="API_ERROR",
                status_code=response.status_code
            )
        
        return response.json()
    
    def parse_item_response(self, data: dict[str, Any], item_id: str) -> CollectionResult:
        """
        Parse eBay API response into CollectionResult.
        
        Args:
            data: Raw API response
            item_id: eBay item ID
            
        Returns:
            Parsed CollectionResult
        """
        try:
            # Extract price information
            price_info = data.get("price", {})
            price_value = Decimal(str(price_info.get("value", "0")))
            currency = price_info.get("currency", "USD")
            
            # Extract shipping cost
            shipping_info = data.get("shippingOptions", [{}])[0] if data.get("shippingOptions") else {}
            shipping_cost_info = shipping_info.get("shippingCost", {})
            shipping_fee = Decimal(str(shipping_cost_info.get("value", "0")))
            
            # Check for original price (sale)
            original_price_info = data.get("marketingPrice", {}).get("originalPrice", {})
            original_price = None
            is_sale = False
            if original_price_info:
                original_price = Decimal(str(original_price_info.get("value", "0")))
                is_sale = original_price > price_value
            
            # Build price data
            price_data = PriceData(
                price=price_value,
                shipping_fee=shipping_fee,
                currency=currency
            )
            
            # Build normalized price (assuming USD for now)
            normalized = NormalizedPrice(
                normalized_price=price_value,
                normalized_total=price_value + shipping_fee,
                currency="USD",
                includes_shipping=False,
                includes_tax=False
            )
            
            # Parse condition
            condition_str = data.get("condition", "").upper()
            condition_map = {
                "NEW": ItemCondition.NEW,
                "LIKE_NEW": ItemCondition.REFURBISHED,
                "VERY_GOOD": ItemCondition.USED,
                "GOOD": ItemCondition.USED,
                "ACCEPTABLE": ItemCondition.USED,
                "FOR_PARTS": ItemCondition.FOR_PARTS,
            }
            condition = condition_map.get(condition_str, ItemCondition.UNKNOWN)
            
            # Parse listing type
            buying_options = data.get("buyingOptions", [])
            if "AUCTION" in buying_options:
                if "FIXED_PRICE" in buying_options:
                    listing_type = ListingType.AUCTION_WITH_BIN
                else:
                    listing_type = ListingType.AUCTION
            else:
                listing_type = ListingType.BUY_IT_NOW
            
            # Build metadata
            metadata = ItemMetadata(
                title=data.get("title", "Unknown"),
                seller_id=data.get("seller", {}).get("username"),
                seller_name=data.get("seller", {}).get("username"),
                condition=condition,
                listing_type=listing_type,
                image_url=data.get("image", {}).get("imageUrl"),
                category=data.get("categoryPath")
            )
            
            # Auction info
            bid_count = None
            auction_end_time = None
            if listing_type in [ListingType.AUCTION, ListingType.AUCTION_WITH_BIN]:
                bid_count = data.get("bidCount", 0)
                end_date_str = data.get("itemEndDate")
                if end_date_str:
                    # Parse ISO format date
                    auction_end_time = datetime.fromisoformat(
                        end_date_str.replace("Z", "+00:00")
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
                collection_method=CollectionMethod.API
            )
            
        except Exception as e:
            return CollectionResult(
                success=False,
                store=StoreType.EBAY,
                item_id=item_id,
                error_code="PARSE_ERROR",
                error_message=str(e),
                collection_method=CollectionMethod.API
            )
    
    async def collect_price(self, item_id: str) -> CollectionResult:
        """
        Collect price information for an eBay item.
        
        Args:
            item_id: eBay item ID
            
        Returns:
            CollectionResult with price data
        """
        try:
            data = await self.get_item(item_id)
            return self.parse_item_response(data, item_id)
        except EbayApiError as e:
            return CollectionResult(
                success=False,
                store=StoreType.EBAY,
                item_id=item_id,
                error_code=e.code,
                error_message=e.message,
                collection_method=CollectionMethod.API
            )
        except Exception as e:
            return CollectionResult(
                success=False,
                store=StoreType.EBAY,
                item_id=item_id,
                error_code="UNKNOWN_ERROR",
                error_message=str(e),
                collection_method=CollectionMethod.API
            )
