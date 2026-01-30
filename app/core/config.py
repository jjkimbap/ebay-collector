"""
Application configuration module.
Loads settings from environment variables with validation.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
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
    app_port: int = 8000
    
    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/price_collector"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_cache_ttl: int = 3600  # 1 hour
    
    # eBay API
    ebay_app_id: str = ""
    ebay_cert_id: str = ""
    ebay_dev_id: str = ""
    ebay_sandbox_mode: bool = True
    ebay_api_base_url: str = "https://api.ebay.com"
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst: int = 10
    
    # Price Collection
    collection_interval_minutes: int = 60
    price_history_retention_days: int = 365
    
    # Currency
    default_currency: str = "USD"
    
    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    @property
    def ebay_api_configured(self) -> bool:
        return bool(self.ebay_app_id and self.ebay_cert_id)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
