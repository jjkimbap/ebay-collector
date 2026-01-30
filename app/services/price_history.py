"""
Price history service.
Handles storage and retrieval of price history data.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import (
    ItemCondition,
    ListingType,
    PriceAlert,
    PriceHistory,
    StoreType,
    TrackedItem,
)
from app.models.schemas import (
    CollectionResult,
    PriceHistoryResponse,
    PriceData,
)

logger = structlog.get_logger()


class PriceHistoryService:
    """Service for managing price history data."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save_price(
        self,
        result: CollectionResult,
        normalized_currency: str = "USD"
    ) -> PriceHistory:
        """Save collected price to history."""
        if not result.success or not result.price_data:
            raise ValueError("Cannot save unsuccessful collection result")
        
        price_record = PriceHistory(
            store=StoreType(result.store.value),
            item_id=result.item_id,
            price=result.price_data.price,
            shipping_fee=result.price_data.shipping_fee,
            currency=result.price_data.currency,
            normalized_price=result.normalized_price.normalized_price if result.normalized_price else result.price_data.price,
            normalized_total=result.normalized_price.normalized_total if result.normalized_price else result.price_data.total_price,
            normalized_currency=normalized_currency,
            includes_shipping=result.normalized_price.includes_shipping if result.normalized_price else False,
            includes_tax=result.normalized_price.includes_tax if result.normalized_price else False,
            is_sale_price=False,
            bid_count=result.bid_count,
            auction_end_time=result.auction_end_time,
            collected_at=result.collected_at,
            collection_method=result.collection_method.value,
        )
        
        self.session.add(price_record)
        await self.session.commit()
        await self.session.refresh(price_record)
        
        logger.info(
            "Price saved to history",
            store=result.store.value,
            item_id=result.item_id,
            price=str(result.price_data.price)
        )
        
        return price_record
    
    async def get_or_create_tracked_item(
        self,
        result: CollectionResult,
        url: str
    ) -> TrackedItem:
        """Get or create a tracked item record."""
        stmt = select(TrackedItem).where(
            and_(
                TrackedItem.store == StoreType(result.store.value),
                TrackedItem.item_id == result.item_id
            )
        )
        existing = await self.session.execute(stmt)
        tracked = existing.scalar_one_or_none()
        
        if tracked:
            if result.metadata:
                tracked.title = result.metadata.title
                tracked.seller_id = result.metadata.seller_id
                tracked.seller_name = result.metadata.seller_name
                tracked.condition = ItemCondition(result.metadata.condition.value)
                tracked.listing_type = ListingType(result.metadata.listing_type.value)
                if result.metadata.image_url:
                    tracked.image_url = str(result.metadata.image_url)
            
            tracked.last_collected_at = datetime.utcnow()
            tracked.collection_error_count = 0
            await self.session.commit()
            return tracked
        
        tracked = TrackedItem(
            store=StoreType(result.store.value),
            item_id=result.item_id,
            title=result.metadata.title if result.metadata else None,
            seller_id=result.metadata.seller_id if result.metadata else None,
            seller_name=result.metadata.seller_name if result.metadata else None,
            condition=ItemCondition(result.metadata.condition.value) if result.metadata else ItemCondition.UNKNOWN,
            listing_type=ListingType(result.metadata.listing_type.value) if result.metadata else ListingType.BUY_IT_NOW,
            item_url=url,
            image_url=str(result.metadata.image_url) if result.metadata and result.metadata.image_url else None,
            is_active=True,
            last_collected_at=datetime.utcnow(),
        )
        
        self.session.add(tracked)
        await self.session.commit()
        await self.session.refresh(tracked)
        
        return tracked
    
    async def get_price_history(
        self,
        store: StoreType,
        item_id: str,
        days: int = 30,
        limit: int = 1000
    ) -> PriceHistoryResponse:
        """Get price history for an item."""
        since = datetime.utcnow() - timedelta(days=days)
        
        stmt = (
            select(PriceHistory)
            .where(
                and_(
                    PriceHistory.store == store,
                    PriceHistory.item_id == item_id,
                    PriceHistory.collected_at >= since
                )
            )
            .order_by(desc(PriceHistory.collected_at))
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        records = result.scalars().all()
        
        if not records:
            return PriceHistoryResponse(
                store=store,
                item_id=item_id,
                total_records=0
            )
        
        item_stmt = select(TrackedItem).where(
            and_(
                TrackedItem.store == store,
                TrackedItem.item_id == item_id
            )
        )
        item_result = await self.session.execute(item_stmt)
        tracked_item = item_result.scalar_one_or_none()
        
        prices = [r.normalized_total for r in records]
        current = records[0]
        lowest_record = min(records, key=lambda r: r.normalized_total)
        highest_record = max(records, key=lambda r: r.normalized_total)
        avg_price = sum(prices) / len(prices)
        
        price_24h_ago = None
        for record in records:
            if record.collected_at <= datetime.utcnow() - timedelta(hours=24):
                price_24h_ago = record.normalized_total
                break
        
        price_change_24h = None
        price_change_pct_24h = None
        if price_24h_ago:
            price_change_24h = current.normalized_total - price_24h_ago
            if price_24h_ago > 0:
                price_change_pct_24h = (price_change_24h / price_24h_ago) * 100
        
        return PriceHistoryResponse(
            store=store,
            item_id=item_id,
            title=tracked_item.title if tracked_item else None,
            current_price=PriceData(
                price=current.price,
                shipping_fee=current.shipping_fee,
                currency=current.currency
            ),
            lowest_price=PriceData(
                price=lowest_record.price,
                shipping_fee=lowest_record.shipping_fee,
                currency=lowest_record.currency
            ),
            highest_price=PriceData(
                price=highest_record.price,
                shipping_fee=highest_record.shipping_fee,
                currency=highest_record.currency
            ),
            average_price=Decimal(str(round(avg_price, 2))),
            price_change_24h=price_change_24h,
            price_change_percentage_24h=Decimal(str(round(price_change_pct_24h, 2))) if price_change_pct_24h else None,
            history=[
                {
                    "price": float(r.price),
                    "shipping_fee": float(r.shipping_fee),
                    "total": float(r.normalized_total),
                    "currency": r.currency,
                    "collected_at": r.collected_at.isoformat()
                }
                for r in records
            ],
            total_records=len(records)
        )
    
    async def create_price_alert(
        self,
        store: StoreType,
        item_id: str,
        target_price: Optional[Decimal] = None,
        price_drop_percentage: Optional[Decimal] = None,
        notification_email: Optional[str] = None
    ) -> PriceAlert:
        """Create a price alert for an item."""
        alert = PriceAlert(
            store=store,
            item_id=item_id,
            target_price=target_price,
            price_drop_percentage=price_drop_percentage,
            is_active=True,
            notification_email=notification_email
        )
        
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        
        return alert
    
    async def check_price_alerts(
        self,
        store: StoreType,
        item_id: str,
        current_price: Decimal
    ) -> list[PriceAlert]:
        """Check if any price alerts should be triggered."""
        stmt = select(PriceAlert).where(
            and_(
                PriceAlert.store == store,
                PriceAlert.item_id == item_id,
                PriceAlert.is_active == True
            )
        )
        
        result = await self.session.execute(stmt)
        alerts = result.scalars().all()
        
        triggered = []
        
        for alert in alerts:
            should_trigger = False
            
            if alert.target_price and current_price <= alert.target_price:
                should_trigger = True
            
            if alert.price_drop_percentage:
                initial_stmt = (
                    select(PriceHistory.normalized_total)
                    .where(
                        and_(
                            PriceHistory.store == store,
                            PriceHistory.item_id == item_id
                        )
                    )
                    .order_by(PriceHistory.collected_at)
                    .limit(1)
                )
                initial_result = await self.session.execute(initial_stmt)
                initial_price = initial_result.scalar_one_or_none()
                
                if initial_price and initial_price > 0:
                    drop_pct = ((initial_price - current_price) / initial_price) * 100
                    if drop_pct >= alert.price_drop_percentage:
                        should_trigger = True
            
            if should_trigger:
                alert.triggered_at = datetime.utcnow()
                alert.is_active = False
                triggered.append(alert)
        
        if triggered:
            await self.session.commit()
        
        return triggered
    
    async def get_items_to_collect(self, limit: int = 100) -> list[TrackedItem]:
        """Get items that need price collection."""
        from app.core.config import get_settings
        settings = get_settings()
        
        threshold = datetime.utcnow() - timedelta(
            minutes=settings.collection_interval_minutes
        )
        
        stmt = (
            select(TrackedItem)
            .where(
                and_(
                    TrackedItem.is_active == True,
                    (
                        (TrackedItem.last_collected_at == None) |
                        (TrackedItem.last_collected_at < threshold)
                    )
                )
            )
            .order_by(TrackedItem.last_collected_at.nulls_first())
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_collection_error(
        self,
        store: StoreType,
        item_id: str
    ) -> None:
        """Mark an item as having a collection error."""
        stmt = select(TrackedItem).where(
            and_(
                TrackedItem.store == store,
                TrackedItem.item_id == item_id
            )
        )
        
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        
        if item:
            item.collection_error_count += 1
            if item.collection_error_count >= 5:
                item.is_active = False
            await self.session.commit()
