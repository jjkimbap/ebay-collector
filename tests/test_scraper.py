"""
Tests for eBay HTML scraper.
"""
import pytest
from decimal import Decimal

from app.collectors.ebay.scraper import EbayScraper
from app.models.schemas import ItemCondition, ListingType, StoreType


class TestEbayScraper:
    """Test cases for eBay scraper."""
    
    @pytest.fixture
    def scraper(self):
        return EbayScraper()
    
    @pytest.fixture
    def sample_html_buy_it_now(self):
        """Sample eBay product page HTML for Buy It Now listing."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Test Product - eBay</title></head>
        <body>
            <h1 class="x-item-title__mainTitle">
                <span>Apple iPhone 14 Pro 256GB Space Black</span>
            </h1>
            
            <div class="x-price-primary">
                <span class="ux-textspans">US $999.99</span>
            </div>
            
            <div class="ux-labels-values--shipping">
                <span class="ux-textspans--BOLD">$12.99</span>
            </div>
            
            <div class="ux-labels-values--condition">
                <span class="ux-textspans">New</span>
            </div>
            
            <a class="ux-seller-section__item--link" href="/usr/tech_seller">
                tech_seller
            </a>
            
            <div class="ux-image-carousel-item">
                <img src="https://i.ebayimg.com/images/g/abc123.jpg" />
            </div>
        </body>
        </html>
        """
    
    @pytest.fixture
    def sample_html_auction(self):
        """Sample eBay product page HTML for auction listing."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Vintage Watch - eBay</title></head>
        <body>
            <h1 class="x-item-title__mainTitle">
                <span>Vintage Rolex Watch 1960s</span>
            </h1>
            
            <div class="x-price-primary">
                <span class="ux-textspans">US $1,500.00</span>
            </div>
            
            <div class="ux-labels-values--shipping">
                <span class="ux-textspans--BOLD">Free</span>
            </div>
            
            <div class="ux-labels-values--condition">
                <span class="ux-textspans">Pre-Owned</span>
            </div>
            
            <span id="bidCount">15 bids</span>
            
            <a class="ux-seller-section__item--link" href="/usr/watch_dealer">
                watch_dealer
            </a>
        </body>
        </html>
        """
    
    @pytest.fixture
    def sample_html_unavailable(self):
        """Sample HTML for unavailable listing."""
        return """
        <!DOCTYPE html>
        <html>
        <body>
            <div class="error__title">
                This listing is no longer available
            </div>
        </body>
        </html>
        """
    
    def test_parse_buy_it_now(self, scraper, sample_html_buy_it_now):
        """Test parsing Buy It Now listing."""
        result = scraper.parse_page(sample_html_buy_it_now, "123456789012")
        
        assert result.success is True
        assert result.store == StoreType.EBAY
        assert result.item_id == "123456789012"
        
        # Price
        assert result.price_data is not None
        assert result.price_data.price == Decimal("999.99")
        assert result.price_data.shipping_fee == Decimal("12.99")
        assert result.price_data.currency == "USD"
        
        # Metadata
        assert result.metadata is not None
        assert "iPhone 14 Pro" in result.metadata.title
        assert result.metadata.condition == ItemCondition.NEW
        assert result.metadata.seller_name == "tech_seller"
        assert result.metadata.listing_type == ListingType.BUY_IT_NOW
    
    def test_parse_auction(self, scraper, sample_html_auction):
        """Test parsing auction listing."""
        result = scraper.parse_page(sample_html_auction, "987654321098")
        
        assert result.success is True
        
        # Price
        assert result.price_data is not None
        assert result.price_data.price == Decimal("1500.00")
        assert result.price_data.shipping_fee == Decimal("0.00")  # Free shipping
        
        # Metadata
        assert result.metadata is not None
        assert "Vintage Rolex" in result.metadata.title
        assert result.metadata.condition == ItemCondition.USED  # Pre-Owned maps to USED
        assert result.metadata.listing_type == ListingType.AUCTION
        
        # Auction info
        assert result.bid_count == 15
    
    def test_parse_unavailable(self, scraper, sample_html_unavailable):
        """Test parsing unavailable listing."""
        result = scraper.parse_page(sample_html_unavailable, "111222333444")
        
        assert result.success is False
        assert result.error_code == "ITEM_UNAVAILABLE"
    
    def test_parse_price_text_usd(self, scraper):
        """Test price text parsing for USD."""
        test_cases = [
            ("$999.99", (Decimal("999.99"), "USD")),
            ("US $1,234.56", (Decimal("1234.56"), "USD")),
            ("$12.00", (Decimal("12.00"), "USD")),
        ]
        
        for text, expected in test_cases:
            result = scraper._parse_price_text(text)
            assert result == expected, f"Text: {text}"
    
    def test_parse_price_text_other_currencies(self, scraper):
        """Test price text parsing for other currencies."""
        test_cases = [
            ("£199.99", (Decimal("199.99"), "GBP")),
            ("€299.99", (Decimal("299.99"), "EUR")),
            ("C$149.99", (Decimal("149.99"), "CAD")),
        ]
        
        for text, expected in test_cases:
            result = scraper._parse_price_text(text)
            assert result == expected, f"Text: {text}"
    
    def test_parse_invalid_html(self, scraper):
        """Test parsing with invalid/empty HTML."""
        result = scraper.parse_page("<html><body></body></html>", "123456789")
        
        assert result.success is False
        assert result.error_code == "PRICE_NOT_FOUND"


class TestEbayScraperIntegration:
    """Integration tests for eBay scraper (requires network)."""
    
    @pytest.fixture
    def scraper(self):
        return EbayScraper()
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires network access")
    async def test_collect_real_item(self, scraper):
        """Test collecting a real eBay item."""
        # Use a known stable listing for testing
        result = await scraper.collect_price("123456789012")
        
        # Just check we get some response
        assert result.store == StoreType.EBAY
        assert result.item_id == "123456789012"
