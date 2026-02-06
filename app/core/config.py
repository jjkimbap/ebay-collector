"""
Application configuration module.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8003
    
    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    
    # eBay API Settings
    ebay_api_url: str = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    ebay_marketplace_id: str = "EBAY_KR"
    ebay_enduserctx: str = "affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>"
    ebay_app_id: str = ""
    ebay_cert_id: str = ""
    # AliExpress API Settings
    ali_api_url: str = "https://api.aliexpress.com/item/search"
    ali_api_key: str = ""
    
    # Amazon API Settings
    amazon_api_url: str = "https://webservices.amazon.com/paapi5/searchitems"
    amazon_access_key: str = ""
    amazon_secret_key: str = ""
    amazon_associate_tag: str = ""

    # Playwright scraping (Unified)
    playwright_headless: bool = False
    playwright_proxy: str = ""
    playwright_amazon_domain: str = "com"
    playwright_ebay_domain: str = "com"
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
