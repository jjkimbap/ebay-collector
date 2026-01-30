"""
Database models for price collection system.
Supports multi-store architecture with eBay as the first implementation.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class StoreType(str, Enum):
    """Supported e-commerce stores."""
    EBAY = "ebay"
    AMAZON = "amazon"  # Future
    WALMART = "walmart"  # Future


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


class TrackedItem(Base):
    """
    Tracked items for price monitoring.
    Stores item metadata and tracking configuration.
    """
    __tablename__ = "tracked_items"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Store identification
    store: Mapped[StoreType] = mapped_column(SQLEnum(StoreType), nullable=False)
    item_id: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Item metadata
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seller_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    seller_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition: Mapped[ItemCondition] = mapped_column(
        SQLEnum(ItemCondition), 
        default=ItemCondition.UNKNOWN
    )
    listing_type: Mapped[ListingType] = mapped_column(
        SQLEnum(ListingType),
        default=ListingType.BUY_IT_NOW
    )
    
    # URLs
    item_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Tracking status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    collection_error_count: Mapped[int] = mapped_column(default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    __table_args__ = (
        Index("idx_tracked_items_store_item", "store", "item_id", unique=True),
        Index("idx_tracked_items_active", "is_active"),
        Index("idx_tracked_items_last_collected", "last_collected_at"),
    )


class PriceHistory(Base):
    """
    Price history records.
    Stores normalized price data with all components.
    """
    __tablename__ = "price_history"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Item reference
    store: Mapped[StoreType] = mapped_column(SQLEnum(StoreType), nullable=False)
    item_id: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Original price data
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    
    # Normalized price (in default currency, usually USD)
    normalized_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    normalized_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    normalized_currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    # Price flags
    includes_shipping: Mapped[bool] = mapped_column(Boolean, default=False)
    includes_tax: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sale_price: Mapped[bool] = mapped_column(Boolean, default=False)
    original_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), 
        nullable=True
    )  # If on sale, original price before discount
    
    # Auction specific (for eBay)
    bid_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    auction_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Collection metadata
    collected_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    collection_method: Mapped[str] = mapped_column(
        String(20), 
        default="api"
    )  # api, scraping
    
    __table_args__ = (
        Index("idx_price_history_store_item", "store", "item_id"),
        Index("idx_price_history_collected", "collected_at"),
        Index("idx_price_history_item_time", "store", "item_id", "collected_at"),
    )


class PriceAlert(Base):
    """
    Price alert configurations.
    Triggers notifications when price conditions are met.
    """
    __tablename__ = "price_alerts"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Item reference
    store: Mapped[StoreType] = mapped_column(SQLEnum(StoreType), nullable=False)
    item_id: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Alert conditions
    target_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    price_drop_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), 
        nullable=True
    )
    
    # Alert status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # User reference (for future user system)
    user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notification_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_price_alerts_store_item", "store", "item_id"),
        Index("idx_price_alerts_active", "is_active"),
    )
