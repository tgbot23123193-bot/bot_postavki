"""
Application configuration module.

Manages all environment variables and application settings with proper validation
and type safety using Pydantic Settings.
"""

import os
from typing import Any, Dict, List, Optional
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    url: str = Field(
        default="sqlite+aiosqlite:///./wb_bot.db",
        description="Database URL for async SQLite connection"
    )
    echo: bool = Field(default=False, description="Enable SQLAlchemy query logging")
    pool_size: int = Field(default=20, description="Connection pool size")
    max_overflow: int = Field(default=30, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=3600, description="Pool recycle time in seconds")
    
    class Config:
        env_prefix = "DB_"


class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    encoding: str = Field(default="utf-8", description="Redis encoding")
    decode_responses: bool = Field(default=True, description="Decode responses")
    socket_timeout: int = Field(default=5, description="Socket timeout in seconds")
    socket_connect_timeout: int = Field(default=5, description="Socket connect timeout")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    health_check_interval: int = Field(default=30, description="Health check interval")
    
    class Config:
        env_prefix = "REDIS_"


class TelegramSettings(BaseSettings):
    """Telegram bot configuration settings."""
    
    bot_token: str = Field(default="8297598368:AAFAjtygKnsIwocwbdC4qTr-lmEFRZ8k4qA", description="Telegram bot token from BotFather")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for production")
    webhook_path: str = Field(default="/webhook", description="Webhook path")
    webhook_secret: Optional[str] = Field(default=None, description="Webhook secret token")
    admin_ids: List[int] = Field(default_factory=list, description="List of admin user IDs")
    max_connections: int = Field(default=100, description="Max webhook connections")
    
    @field_validator('admin_ids', mode='before')
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        """Parse admin IDs from environment variable."""
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v or []
    
    class Config:
        env_prefix = "TG_"


class WildberriesSettings(BaseSettings):
    """Wildberries API configuration settings."""
    
    base_url: str = Field(
        default="https://suppliers-api.wildberries.ru",
        description="WB API base URL"
    )
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Initial retry delay in seconds")
    backoff_factor: float = Field(default=2.0, description="Exponential backoff factor")
    rate_limit_delay: int = Field(default=60, description="Rate limit delay in seconds")
    circuit_breaker_threshold: int = Field(default=5, description="Circuit breaker error threshold")
    circuit_breaker_timeout: int = Field(default=300, description="Circuit breaker timeout in seconds")
    
    # API endpoints
    warehouses_endpoint: str = Field(default="/api/v3/warehouses", description="Warehouses endpoint")
    supplies_endpoint: str = Field(default="/api/v3/supplies", description="Supplies endpoint")
    slots_endpoint: str = Field(default="/api/v3/supplies/slots", description="Slots endpoint")
    
    class Config:
        env_prefix = "WB_"


class MonitoringSettings(BaseSettings):
    """Monitoring and performance settings."""
    
    min_check_interval: int = Field(default=30, description="Minimum check interval in seconds")
    max_check_interval: int = Field(default=1, description="Maximum check interval in seconds")
    default_check_interval: int = Field(default=5, description="Default check interval in seconds")
    cache_ttl: int = Field(default=5, description="Cache TTL in seconds")
    max_concurrent_requests: int = Field(default=1000, description="Max concurrent requests")
    max_api_keys_per_user: int = Field(default=5, description="Max API keys per user")
    trial_bookings_limit: int = Field(default=2, description="Free trial bookings limit")
    
    # Coefficient thresholds
    default_max_coefficient: float = Field(default=2.0, description="Default max coefficient")
    available_coefficients: List[float] = Field(
        default_factory=lambda: [1.0, 2.0, 3.0, 5.0],
        description="Available coefficient options"
    )
    
    class Config:
        env_prefix = "MONITORING_"


class SecuritySettings(BaseSettings):
    """Security and encryption settings."""
    
    encryption_key: str = Field(default="wb_bot_encryption_key_32_chars_long", description="AES encryption key for API keys")
    jwt_secret: str = Field(default="wb_bot_jwt_secret_key_for_tokens_auth", description="JWT secret for tokens")
    jwt_expiration_hours: int = Field(default=24, description="JWT token expiration in hours")
    api_key_validation_timeout: int = Field(default=10, description="API key validation timeout")
    
    @field_validator('encryption_key')
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Validate encryption key length."""
        if len(v) < 32:
            raise ValueError("Encryption key must be at least 32 characters long")
        return v
    
    class Config:
        env_prefix = "SECURITY_"


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""
    
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format: json or text")
    file_path: Optional[str] = Field(default=None, description="Log file path")
    max_file_size: int = Field(default=10485760, description="Max log file size in bytes (10MB)")
    backup_count: int = Field(default=5, description="Number of backup log files")
    enable_access_logs: bool = Field(default=True, description="Enable access logs")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    class Config:
        env_prefix = "LOG_"


class Settings(BaseSettings):
    """Main application settings."""
    
    # Application
    app_name: str = Field(default="WB Auto-Booking Bot", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment: development, staging, production")
    version: str = Field(default="1.0.0", description="Application version")
    
    # Component settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    wildberries: WildberriesSettings = Field(default_factory=WildberriesSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    # Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = ['development', 'staging', 'production']
        if v.lower() not in valid_envs:
            raise ValueError(f"Environment must be one of: {valid_envs}")
        return v.lower()
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    class Config:
        env_file = None  # Отключаем .env файл
        case_sensitive = False
        validate_assignment = True
        extra = "allow"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings


# Export commonly used settings for convenience
def get_database_url() -> str:
    """Get database URL."""
    return settings.database.url


def get_redis_url() -> str:
    """Get Redis URL."""
    return settings.redis.url


def get_bot_token() -> str:
    """Get Telegram bot token."""
    return settings.telegram.bot_token


def get_wb_base_url() -> str:
    """Get Wildberries API base URL."""
    return settings.wildberries.base_url
