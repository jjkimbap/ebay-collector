"""
Currency normalization service.
Converts prices to target currency (default: USD).
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models.schemas import NormalizedPrice, PriceData

logger = structlog.get_logger()


class CurrencyConversionError(Exception):
    """Currency conversion error."""
    pass


class CurrencyService:
    """
    Currency conversion service.
    
    Uses exchange rate API to normalize prices to target currency.
    Caches rates to minimize API calls.
    """
    
    # Free exchange rate API
    API_URL = "https://api.exchangerate-api.com/v4/latest"
    
    # Fallback rates (approximate, for when API is unavailable)
    FALLBACK_RATES = {
        "USD": Decimal("1.0"),
        "EUR": Decimal("1.10"),
        "GBP": Decimal("1.27"),
        "CAD": Decimal("0.74"),
        "AUD": Decimal("0.66"),
        "JPY": Decimal("0.0067"),
    }
    
    def __init__(self):
        self.settings = get_settings()
        self._rates: dict[str, dict[str, Decimal]] = {}
        self._rates_updated: dict[str, datetime] = {}
        self._rate_cache_duration = timedelta(hours=1)
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    def _is_cache_valid(self, base_currency: str) -> bool:
        """Check if cached rates are still valid."""
        if base_currency not in self._rates_updated:
            return False
        
        age = datetime.utcnow() - self._rates_updated[base_currency]
        return age < self._rate_cache_duration
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def _fetch_rates(self, base_currency: str) -> dict[str, Decimal]:
        """Fetch exchange rates from API."""
        client = await self._get_http_client()
        
        response = await client.get(f"{self.API_URL}/{base_currency}")
        
        if response.status_code != 200:
            raise CurrencyConversionError(
                f"Failed to fetch exchange rates: HTTP {response.status_code}"
            )
        
        data = response.json()
        
        # Convert to Decimal for precision
        rates = {}
        for currency, rate in data.get("rates", {}).items():
            rates[currency] = Decimal(str(rate))
        
        return rates
    
    async def get_rate(
        self, 
        from_currency: str, 
        to_currency: str
    ) -> tuple[Decimal, datetime]:
        """
        Get exchange rate between two currencies.
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            
        Returns:
            Tuple of (exchange_rate, rate_date)
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        # Same currency
        if from_currency == to_currency:
            return Decimal("1.0"), datetime.utcnow()
        
        # Check cache
        if not self._is_cache_valid(from_currency):
            try:
                rates = await self._fetch_rates(from_currency)
                self._rates[from_currency] = rates
                self._rates_updated[from_currency] = datetime.utcnow()
            except Exception as e:
                logger.warning(
                    "Failed to fetch rates, using fallback",
                    from_currency=from_currency,
                    error=str(e)
                )
                # Use fallback rates
                return self._get_fallback_rate(from_currency, to_currency)
        
        # Get rate from cache
        rates = self._rates.get(from_currency, {})
        rate = rates.get(to_currency)
        
        if rate is None:
            logger.warning(
                "Rate not found, using fallback",
                from_currency=from_currency,
                to_currency=to_currency
            )
            return self._get_fallback_rate(from_currency, to_currency)
        
        return rate, self._rates_updated[from_currency]
    
    def _get_fallback_rate(
        self, 
        from_currency: str, 
        to_currency: str
    ) -> tuple[Decimal, datetime]:
        """Get approximate fallback rate."""
        # Convert through USD
        from_usd = self.FALLBACK_RATES.get(from_currency, Decimal("1.0"))
        to_usd = self.FALLBACK_RATES.get(to_currency, Decimal("1.0"))
        
        # from_currency -> USD -> to_currency
        rate = from_usd / to_usd
        
        return rate, datetime.utcnow()
    
    async def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str
    ) -> tuple[Decimal, Decimal, datetime]:
        """
        Convert amount between currencies.
        
        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            
        Returns:
            Tuple of (converted_amount, exchange_rate, rate_date)
        """
        rate, rate_date = await self.get_rate(from_currency, to_currency)
        converted = amount * rate
        
        # Round to 2 decimal places
        converted = converted.quantize(Decimal("0.01"))
        
        return converted, rate, rate_date
    
    async def normalize_price(
        self,
        price_data: PriceData,
        target_currency: Optional[str] = None
    ) -> NormalizedPrice:
        """
        Normalize price data to target currency.
        
        Args:
            price_data: Original price data
            target_currency: Target currency (defaults to settings)
            
        Returns:
            NormalizedPrice with converted values
        """
        if target_currency is None:
            target_currency = self.settings.default_currency
        
        # Convert price
        normalized_price, rate, rate_date = await self.convert(
            price_data.price,
            price_data.currency,
            target_currency
        )
        
        # Convert shipping
        normalized_shipping, _, _ = await self.convert(
            price_data.shipping_fee,
            price_data.currency,
            target_currency
        )
        
        return NormalizedPrice(
            normalized_price=normalized_price,
            normalized_total=normalized_price + normalized_shipping,
            currency=target_currency,
            includes_shipping=False,
            includes_tax=False,
            exchange_rate=rate if price_data.currency != target_currency else None,
            exchange_rate_date=rate_date if price_data.currency != target_currency else None
        )


# Singleton instance
_currency_service: Optional[CurrencyService] = None


def get_currency_service() -> CurrencyService:
    """Get currency service singleton."""
    global _currency_service
    if _currency_service is None:
        _currency_service = CurrencyService()
    return _currency_service
