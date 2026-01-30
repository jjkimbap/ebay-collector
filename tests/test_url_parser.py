"""
Tests for eBay URL parser.
"""
import pytest

from app.collectors.ebay.url_parser import EbayUrlParser
from app.models.schemas import StoreType


class TestEbayUrlParser:
    """Test cases for eBay URL parsing."""
    
    def test_is_ebay_url_valid(self):
        """Test valid eBay URLs are recognized."""
        valid_urls = [
            "https://www.ebay.com/itm/123456789012",
            "https://ebay.com/itm/123456789012",
            "https://www.ebay.co.uk/itm/123456789012",
            "https://www.ebay.de/itm/123456789012",
            "https://www.ebay.fr/itm/123456789012",
            "https://www.ebay.ca/itm/123456789012",
        ]
        
        for url in valid_urls:
            assert EbayUrlParser.is_ebay_url(url), f"Should recognize: {url}"
    
    def test_is_ebay_url_invalid(self):
        """Test non-eBay URLs are rejected."""
        invalid_urls = [
            "https://www.amazon.com/dp/B08N5WRWNW",
            "https://www.walmart.com/ip/123456789",
            "https://www.google.com",
            "https://www.fakebay.com/itm/123",
        ]
        
        for url in invalid_urls:
            assert not EbayUrlParser.is_ebay_url(url), f"Should reject: {url}"
    
    def test_extract_item_id_standard(self):
        """Test extracting item ID from standard URLs."""
        test_cases = [
            ("https://www.ebay.com/itm/256123456789", "256123456789"),
            ("https://ebay.com/itm/256123456789", "256123456789"),
            ("https://www.ebay.com/itm/256123456789?hash=item3ba85b7", "256123456789"),
        ]
        
        for url, expected in test_cases:
            result = EbayUrlParser.extract_item_id(url)
            assert result == expected, f"URL: {url}, expected: {expected}, got: {result}"
    
    def test_extract_item_id_with_title(self):
        """Test extracting item ID from URLs with title slug."""
        test_cases = [
            ("https://www.ebay.com/itm/Apple-iPhone-14-Pro-256GB/256123456789", "256123456789"),
            ("https://www.ebay.com/itm/Some-Product-Name-Here/123456789012?var=123", "123456789012"),
        ]
        
        for url, expected in test_cases:
            result = EbayUrlParser.extract_item_id(url)
            assert result == expected, f"URL: {url}, expected: {expected}, got: {result}"
    
    def test_extract_item_id_invalid(self):
        """Test that invalid URLs return None."""
        invalid_urls = [
            "https://www.ebay.com/sch/i.html?_nkw=iphone",
            "https://www.ebay.com/usr/seller123",
            "https://www.ebay.com/b/Electronics/12345",
        ]
        
        for url in invalid_urls:
            result = EbayUrlParser.extract_item_id(url)
            assert result is None, f"Should return None for: {url}"
    
    def test_get_region(self):
        """Test region extraction from URLs."""
        test_cases = [
            ("https://www.ebay.com/itm/123", "US"),
            ("https://www.ebay.co.uk/itm/123", "UK"),
            ("https://www.ebay.de/itm/123", "DE"),
            ("https://www.ebay.fr/itm/123", "FR"),
            ("https://www.ebay.ca/itm/123", "CA"),
        ]
        
        for url, expected in test_cases:
            result = EbayUrlParser.get_region(url)
            assert result == expected, f"URL: {url}, expected: {expected}, got: {result}"
    
    def test_build_canonical_url(self):
        """Test canonical URL building."""
        test_cases = [
            ("256123456789", "US", "https://www.ebay.com/itm/256123456789"),
            ("256123456789", "UK", "https://www.ebay.co.uk/itm/256123456789"),
            ("256123456789", "DE", "https://www.ebay.de/itm/256123456789"),
        ]
        
        for item_id, region, expected in test_cases:
            result = EbayUrlParser.build_canonical_url(item_id, region)
            assert result == expected
    
    def test_parse_success(self):
        """Test full URL parsing success."""
        url = "https://www.ebay.com/itm/Some-Product/256123456789?var=123"
        result = EbayUrlParser.parse(url)
        
        assert result.success is True
        assert result.store == StoreType.EBAY
        assert result.item_id == "256123456789"
        assert result.canonical_url == "https://www.ebay.com/itm/256123456789"
    
    def test_parse_failure_not_ebay(self):
        """Test parsing failure for non-eBay URL."""
        url = "https://www.amazon.com/dp/B08N5WRWNW"
        result = EbayUrlParser.parse(url)
        
        assert result.success is False
        assert result.error == "Not a valid eBay URL"
    
    def test_parse_failure_no_item_id(self):
        """Test parsing failure when item ID can't be extracted."""
        url = "https://www.ebay.com/sch/i.html?_nkw=iphone"
        result = EbayUrlParser.parse(url)
        
        assert result.success is False
        assert "Could not extract item ID" in result.error
    
    def test_validate_item_id(self):
        """Test item ID validation."""
        valid_ids = [
            "123456789",
            "256123456789",
            "123456789012345",
        ]
        
        invalid_ids = [
            "12345678",  # Too short
            "1234567890123456",  # Too long
            "123abc456",  # Contains letters
            "",
        ]
        
        for item_id in valid_ids:
            assert EbayUrlParser.validate_item_id(item_id), f"Should be valid: {item_id}"
        
        for item_id in invalid_ids:
            assert not EbayUrlParser.validate_item_id(item_id), f"Should be invalid: {item_id}"
