"""
eBay URL parsing utilities.
Extracts itemId from various eBay URL formats.
"""
import re
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

from app.models.schemas import StoreType, UrlParseResponse


class EbayUrlParser:
    """
    Parser for eBay product URLs.
    
    Supported URL formats:
    - https://www.ebay.com/itm/256123456789
    - https://www.ebay.com/itm/product-title/256123456789
    - https://www.ebay.com/itm/256123456789?var=...
    - https://ebay.com/itm/256123456789
    - Regional domains: ebay.co.uk, ebay.de, ebay.fr, etc.
    """
    
    # eBay domains by region
    SUPPORTED_DOMAINS = [
        "ebay.com",
        "ebay.co.uk",
        "ebay.de",
        "ebay.fr",
        "ebay.ca",
        "ebay.com.au",
        "ebay.it",
        "ebay.es",
        "ebay.nl",
        "ebay.be",
        "ebay.at",
        "ebay.ch",
        "ebay.ie",
        "ebay.pl",
        "ebay.ph",
        "ebay.com.sg",
        "ebay.com.my",
        "ebay.co.jp",
    ]
    
    # URL patterns for item ID extraction
    ITEM_URL_PATTERN = re.compile(
        r"/itm/(?:[^/]+/)?(\d{9,15})(?:\?|$|#)",
        re.IGNORECASE
    )
    
    # Alternative pattern for p/ URLs
    P_URL_PATTERN = re.compile(
        r"/p/(\d+)",
        re.IGNORECASE
    )
    
    # Item ID validation pattern
    ITEM_ID_PATTERN = re.compile(r"^\d{9,15}$")
    
    @classmethod
    def is_ebay_url(cls, url: str) -> bool:
        """Check if URL is from an eBay domain."""
        try:
            parsed = urlparse(url.lower())
            host = parsed.netloc.replace("www.", "")
            return any(host == domain or host.endswith(f".{domain}") 
                      for domain in cls.SUPPORTED_DOMAINS)
        except Exception:
            return False
    
    @classmethod
    def extract_item_id(cls, url: str) -> Optional[str]:
        """
        Extract eBay item ID from URL.
        
        Args:
            url: eBay product URL
            
        Returns:
            Item ID string or None if not found
        """
        # Try main /itm/ pattern
        match = cls.ITEM_URL_PATTERN.search(url)
        if match:
            return match.group(1)
        
        # Try query parameter fallback
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Check for item= or itemId= parameter
        for param in ["item", "itemId", "itemid"]:
            if param in query_params:
                item_id = query_params[param][0]
                if cls.ITEM_ID_PATTERN.match(item_id):
                    return item_id
        
        return None
    
    @classmethod
    def get_region(cls, url: str) -> str:
        """
        Get eBay region from URL.
        
        Returns region code (e.g., 'US', 'UK', 'DE')
        """
        try:
            parsed = urlparse(url.lower())
            host = parsed.netloc.replace("www.", "")
            
            region_map = {
                "ebay.com": "US",
                "ebay.co.uk": "UK",
                "ebay.de": "DE",
                "ebay.fr": "FR",
                "ebay.ca": "CA",
                "ebay.com.au": "AU",
                "ebay.it": "IT",
                "ebay.es": "ES",
                "ebay.nl": "NL",
                "ebay.be": "BE",
                "ebay.at": "AT",
                "ebay.ch": "CH",
                "ebay.ie": "IE",
                "ebay.pl": "PL",
                "ebay.ph": "PH",
                "ebay.com.sg": "SG",
                "ebay.com.my": "MY",
                "ebay.co.jp": "JP",
            }
            
            for domain, region in region_map.items():
                if host == domain or host.endswith(f".{domain}"):
                    return region
            
            return "US"  # Default
        except Exception:
            return "US"
    
    @classmethod
    def build_canonical_url(cls, item_id: str, region: str = "US") -> str:
        """
        Build canonical eBay URL for an item.
        
        Args:
            item_id: eBay item ID
            region: Region code
            
        Returns:
            Canonical URL string
        """
        domain_map = {
            "US": "www.ebay.com",
            "UK": "www.ebay.co.uk",
            "DE": "www.ebay.de",
            "FR": "www.ebay.fr",
            "CA": "www.ebay.ca",
            "AU": "www.ebay.com.au",
            "IT": "www.ebay.it",
            "ES": "www.ebay.es",
        }
        
        domain = domain_map.get(region, "www.ebay.com")
        return f"https://{domain}/itm/{item_id}"
    
    @classmethod
    def parse(cls, url: str) -> UrlParseResponse:
        """
        Parse eBay URL and extract all relevant information.
        
        Args:
            url: URL to parse
            
        Returns:
            UrlParseResponse with parsing results
        """
        # Validate it's an eBay URL
        if not cls.is_ebay_url(url):
            return UrlParseResponse(
                success=False,
                original_url=url,
                error="Not a valid eBay URL"
            )
        
        # Extract item ID
        item_id = cls.extract_item_id(url)
        if not item_id:
            return UrlParseResponse(
                success=False,
                original_url=url,
                error="Could not extract item ID from URL"
            )
        
        # Get region and build canonical URL
        region = cls.get_region(url)
        canonical_url = cls.build_canonical_url(item_id, region)
        
        return UrlParseResponse(
            success=True,
            store=StoreType.EBAY,
            item_id=item_id,
            original_url=url,
            canonical_url=canonical_url
        )
    
    @classmethod
    def validate_item_id(cls, item_id: str) -> bool:
        """
        Validate eBay item ID format.
        
        Args:
            item_id: Item ID to validate
            
        Returns:
            True if valid format
        """
        return bool(cls.ITEM_ID_PATTERN.match(item_id))
