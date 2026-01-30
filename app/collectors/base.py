"""
Base collector interface for multi-store price collection.
All store-specific collectors should implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.models.schemas import (
    CollectionResult,
    StoreIdentifier,
    StoreType,
    UrlParseResponse,
)


class BaseCollector(ABC):
    """
    Abstract base class for store-specific price collectors.
    
    Each store (eBay, Amazon, Walmart, etc.) should implement this interface
    to ensure consistent behavior across the system.
    """
    
    @property
    @abstractmethod
    def store_type(self) -> StoreType:
        """Return the store type this collector handles."""
        pass
    
    @property
    @abstractmethod
    def supported_domains(self) -> list[str]:
        """Return list of domains this collector can handle."""
        pass
    
    @abstractmethod
    async def parse_url(self, url: str) -> UrlParseResponse:
        """
        Parse a product URL and extract store identifier.
        
        Args:
            url: Product URL to parse
            
        Returns:
            UrlParseResponse with parsed identifier or error
        """
        pass
    
    @abstractmethod
    async def collect_price(
        self, 
        identifier: StoreIdentifier,
        use_fallback: bool = True
    ) -> CollectionResult:
        """
        Collect price information for a product.
        
        Args:
            identifier: Store-specific product identifier
            use_fallback: Whether to use fallback method (scraping) if primary fails
            
        Returns:
            CollectionResult with price data or error
        """
        pass
    
    @abstractmethod
    async def validate_item_exists(self, identifier: StoreIdentifier) -> bool:
        """
        Check if an item exists and is available.
        
        Args:
            identifier: Store-specific product identifier
            
        Returns:
            True if item exists and is available
        """
        pass
    
    def can_handle_url(self, url: str) -> bool:
        """
        Check if this collector can handle a given URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if this collector can handle the URL
        """
        return any(domain in url.lower() for domain in self.supported_domains)


class CollectorRegistry:
    """
    Registry for store collectors.
    Manages collector instances and URL routing.
    """
    
    _collectors: dict[StoreType, BaseCollector] = {}
    
    @classmethod
    def register(cls, collector: BaseCollector) -> None:
        """Register a collector for a store type."""
        cls._collectors[collector.store_type] = collector
    
    @classmethod
    def get_collector(cls, store_type: StoreType) -> Optional[BaseCollector]:
        """Get collector for a specific store type."""
        return cls._collectors.get(store_type)
    
    @classmethod
    def get_collector_for_url(cls, url: str) -> Optional[BaseCollector]:
        """Find the appropriate collector for a URL."""
        for collector in cls._collectors.values():
            if collector.can_handle_url(url):
                return collector
        return None
    
    @classmethod
    def get_all_collectors(cls) -> list[BaseCollector]:
        """Get all registered collectors."""
        return list(cls._collectors.values())
    
    @classmethod
    def supported_stores(cls) -> list[StoreType]:
        """Get list of supported store types."""
        return list(cls._collectors.keys())
