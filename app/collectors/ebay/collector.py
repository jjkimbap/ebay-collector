"""
eBay price collector implementation.
Combines API client and scraper with fallback logic.
"""
import structlog

from app.collectors.base import BaseCollector, CollectorRegistry
from app.collectors.ebay.api_client import EbayApiClient
from app.collectors.ebay.scraper import EbayScraper
from app.collectors.ebay.url_parser import EbayUrlParser
from app.core.config import get_settings
from app.models.schemas import (
    CollectionResult,
    EbayIdentifier,
    StoreIdentifier,
    StoreType,
    UrlParseResponse,
)

logger = structlog.get_logger()


class EbayCollector(BaseCollector):
    """
    eBay price collector.
    
    Primary collection via eBay Browse API with HTML scraping fallback.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._api_client: EbayApiClient | None = None
        self._scraper: EbayScraper | None = None
    
    @property
    def store_type(self) -> StoreType:
        return StoreType.EBAY
    
    @property
    def supported_domains(self) -> list[str]:
        return EbayUrlParser.SUPPORTED_DOMAINS
    
    @property
    def api_client(self) -> EbayApiClient:
        if self._api_client is None:
            self._api_client = EbayApiClient()
        return self._api_client
    
    @property
    def scraper(self) -> EbayScraper:
        if self._scraper is None:
            self._scraper = EbayScraper()
        return self._scraper
    
    async def close(self):
        """Close all clients."""
        if self._api_client:
            await self._api_client.close()
        if self._scraper:
            await self._scraper.close()
    
    async def parse_url(self, url: str) -> UrlParseResponse:
        """Parse eBay product URL to extract item ID."""
        return EbayUrlParser.parse(url)
    
    async def validate_item_exists(self, identifier: StoreIdentifier) -> bool:
        """
        Validate that an eBay item exists.
        
        Tries API first, then scraping as fallback.
        """
        if identifier.store != StoreType.EBAY:
            return False
        
        # Try API first
        if self.settings.ebay_api_configured:
            try:
                result = await self.api_client.collect_price(identifier.item_id)
                return result.success
            except Exception as e:
                logger.warning(
                    "API validation failed, trying scraper",
                    item_id=identifier.item_id,
                    error=str(e)
                )
        
        # Fallback to scraper
        try:
            result = await self.scraper.collect_price(identifier.item_id)
            return result.success
        except Exception as e:
            logger.error(
                "Scraper validation failed",
                item_id=identifier.item_id,
                error=str(e)
            )
            return False
    
    async def collect_price(
        self,
        identifier: StoreIdentifier,
        use_fallback: bool = True
    ) -> CollectionResult:
        """
        Collect price for an eBay item.
        
        Strategy:
        1. Try eBay Browse API (if configured)
        2. If API fails and use_fallback=True, try HTML scraping
        
        Args:
            identifier: eBay item identifier
            use_fallback: Whether to use scraping as fallback
            
        Returns:
            CollectionResult with price data or error
        """
        if identifier.store != StoreType.EBAY:
            return CollectionResult(
                success=False,
                store=identifier.store,
                item_id=identifier.item_id,
                error_code="INVALID_STORE",
                error_message=f"Expected eBay store, got {identifier.store}"
            )
        
        item_id = identifier.item_id
        
        # Validate item ID format
        if not EbayUrlParser.validate_item_id(item_id):
            return CollectionResult(
                success=False,
                store=StoreType.EBAY,
                item_id=item_id,
                error_code="INVALID_ITEM_ID",
                error_message=f"Invalid eBay item ID format: {item_id}"
            )
        
        logger.info("Starting price collection", item_id=item_id, store="ebay")
        
        # Try API first
        if self.settings.ebay_api_configured:
            logger.debug("Attempting API collection", item_id=item_id)
            
            result = await self.api_client.collect_price(item_id)
            
            if result.success:
                logger.info(
                    "API collection successful",
                    item_id=item_id,
                    price=str(result.price_data.price) if result.price_data else None
                )
                return result
            
            logger.warning(
                "API collection failed",
                item_id=item_id,
                error_code=result.error_code,
                error_message=result.error_message
            )
        else:
            logger.debug("API not configured, skipping", item_id=item_id)
        
        # Fallback to scraping
        if use_fallback:
            logger.debug("Attempting scraper fallback", item_id=item_id)
            
            result = await self.scraper.collect_price(item_id)
            
            if result.success:
                logger.info(
                    "Scraper collection successful",
                    item_id=item_id,
                    price=str(result.price_data.price) if result.price_data else None
                )
            else:
                logger.error(
                    "Scraper collection failed",
                    item_id=item_id,
                    error_code=result.error_code,
                    error_message=result.error_message
                )
            
            return result
        
        # No fallback and API failed
        return CollectionResult(
            success=False,
            store=StoreType.EBAY,
            item_id=item_id,
            error_code="COLLECTION_FAILED",
            error_message="API collection failed and fallback is disabled"
        )
    
    async def collect_price_from_url(
        self,
        url: str,
        use_fallback: bool = True
    ) -> CollectionResult:
        """
        Collect price from eBay product URL.
        
        Convenience method that parses URL and collects price.
        
        Args:
            url: eBay product URL
            use_fallback: Whether to use scraping as fallback
            
        Returns:
            CollectionResult with price data or error
        """
        # Parse URL
        parse_result = await self.parse_url(url)
        
        if not parse_result.success:
            return CollectionResult(
                success=False,
                store=StoreType.EBAY,
                item_id="",
                error_code="URL_PARSE_ERROR",
                error_message=parse_result.error
            )
        
        # Build identifier and collect
        identifier = EbayIdentifier(item_id=parse_result.item_id)
        return await self.collect_price(identifier, use_fallback)


# Register eBay collector
def register_ebay_collector():
    """Register eBay collector in the registry."""
    collector = EbayCollector()
    CollectorRegistry.register(collector)
    return collector
