"""
Pydantic schemas for API request/response models.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class StoreType(str, Enum):
    """Supported e-commerce stores."""
    EBAY = "ebay"
    AMAZON = "amazon"
    WALMART = "walmart"


class ItemCondition(str, Enum):
    """Item condition types."""
    NEW = "new"
    USED = "used"
    REFURBISHED = "refurbished"
    FOR_PARTS = "for_parts"
    UNKNOWN = "unknown"


class ListingType(str, Enum):
    """eBay listing types."""
    BUY_IT_NOW = "buy_it_now"
    AUCTION = "auction"
    AUCTION_WITH_BIN = "auction_with_bin"


class CollectionMethod(str, Enum):
    """Price collection methods."""
    API = "api"
    SCRAPING = "scraping"


# ==================== Store Identifier ====================

class StoreIdentifier(BaseModel):
    """Base store identifier."""
    store: StoreType
    item_id: str = Field(..., min_length=1, max_length=50)


class EbayIdentifier(StoreIdentifier):
    """eBay specific identifier."""
    store: StoreType = StoreType.EBAY
    item_id: str = Field(..., pattern=r"^\d{9,15}$", description="eBay item ID (9-15 digits)")


# ==================== URL Parsing ====================

class UrlParseRequest(BaseModel):
    """Request to parse a product URL."""
    url: HttpUrl = Field(
        ...,
        examples=["https://www.ebay.com/itm/256123456789"],
        description="eBay 상품 URL"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://www.ebay.com/itm/256123456789"
                },
                {
                    "url": "https://www.ebay.com/itm/Apple-iPhone-14-Pro-256GB/256123456789"
                }
            ]
        }
    }
    
    @field_validator("url")
    @classmethod
    def validate_ebay_url(cls, v: HttpUrl) -> HttpUrl:
        url_str = str(v)
        valid_domains = ["ebay.com", "ebay.co.uk", "ebay.de", "ebay.fr", "ebay.ca"]
        if not any(domain in url_str for domain in valid_domains):
            # For now, only validate eBay URLs
            # Future: extend for other stores
            pass
        return v


class UrlParseResponse(BaseModel):
    """Response from URL parsing."""
    success: bool
    store: Optional[StoreType] = None
    item_id: Optional[str] = None
    original_url: str
    canonical_url: Optional[str] = None
    error: Optional[str] = None


# ==================== Price Data ====================

class PriceData(BaseModel):
    """Raw price data from collection."""
    price: Decimal = Field(..., ge=0, decimal_places=2)
    shipping_fee: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    currency: str = Field(..., min_length=3, max_length=3)
    
    # Calculated
    total_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    
    def model_post_init(self, __context) -> None:
        if self.total_price == Decimal("0.00"):
            object.__setattr__(self, "total_price", self.price + self.shipping_fee)


class NormalizedPrice(BaseModel):
    """Normalized price in target currency."""
    normalized_price: Decimal = Field(..., ge=0, decimal_places=2)
    normalized_total: Decimal = Field(..., ge=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    includes_shipping: bool = False
    includes_tax: bool = False
    exchange_rate: Optional[Decimal] = None
    exchange_rate_date: Optional[datetime] = None


# ==================== Item Metadata ====================

class ItemMetadata(BaseModel):
    """Product metadata."""
    title: str = Field(..., min_length=1, max_length=500)
    seller_id: Optional[str] = None
    seller_name: Optional[str] = None
    condition: ItemCondition = ItemCondition.UNKNOWN
    listing_type: ListingType = ListingType.BUY_IT_NOW
    image_url: Optional[HttpUrl] = None
    category: Optional[str] = None


# ==================== Collection Results ====================

class CollectionResult(BaseModel):
    """Result from price collection."""
    success: bool
    store: StoreType
    item_id: str
    
    # Data (if successful)
    metadata: Optional[ItemMetadata] = None
    price_data: Optional[PriceData] = None
    normalized_price: Optional[NormalizedPrice] = None
    
    # Auction specific
    bid_count: Optional[int] = None
    auction_end_time: Optional[datetime] = None
    is_auction_ended: bool = False
    
    # Collection info
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    collection_method: CollectionMethod = CollectionMethod.API
    
    # Error info (if failed)
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# ==================== API Requests ====================

class CollectPriceRequest(BaseModel):
    """Request to collect price for a URL."""
    url: HttpUrl = Field(
        ...,
        examples=["https://www.ebay.com/itm/256123456789"],
        description="eBay 상품 URL"
    )
    force_refresh: bool = Field(
        default=False, 
        description="캐시를 무시하고 새로 수집"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://www.ebay.com/itm/256123456789",
                    "force_refresh": False
                }
            ]
        }
    }


class TrackItemRequest(BaseModel):
    """Request to start tracking an item."""
    url: HttpUrl = Field(
        ...,
        examples=["https://www.ebay.com/itm/256123456789"],
        description="eBay 상품 URL"
    )
    notification_email: Optional[str] = Field(
        default=None, 
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        examples=["user@example.com"],
        description="알림을 받을 이메일 주소"
    )
    target_price: Optional[Decimal] = Field(
        default=None, 
        ge=0,
        examples=[800.00],
        description="목표 가격 (이 가격 이하로 떨어지면 알림)"
    )
    price_drop_percentage: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        le=100,
        examples=[10.0],
        description="가격 하락 비율 (%) (이 비율만큼 떨어지면 알림)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://www.ebay.com/itm/256123456789",
                    "notification_email": "user@example.com",
                    "target_price": 800.00
                },
                {
                    "url": "https://www.ebay.com/itm/256123456789",
                    "price_drop_percentage": 10.0
                }
            ]
        }
    }


# ==================== API Responses ====================

class CollectPriceResponse(BaseModel):
    """Response from price collection."""
    success: bool
    data: Optional[CollectionResult] = None
    cached: bool = False
    error: Optional[str] = None


class TrackItemResponse(BaseModel):
    """Response from item tracking registration."""
    success: bool
    tracking_id: Optional[int] = None
    item_id: Optional[str] = None
    store: Optional[StoreType] = None
    message: str


class PriceHistoryResponse(BaseModel):
    """Price history for an item."""
    store: StoreType
    item_id: str
    title: Optional[str] = None
    current_price: Optional[PriceData] = None
    lowest_price: Optional[PriceData] = None
    highest_price: Optional[PriceData] = None
    average_price: Optional[Decimal] = None
    price_change_24h: Optional[Decimal] = None
    price_change_percentage_24h: Optional[Decimal] = None
    history: list[dict] = Field(default_factory=list)
    total_records: int = 0


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    database: str
    redis: str
    ebay_api: str
