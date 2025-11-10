"""Application configuration via Pydantic settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Tuina Booking API"
    debug: bool = False

    database_url: str = Field(..., alias="DATABASE_URL")
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expires_in_minutes: int = Field(60 * 24, alias="JWT_EXPIRES_IN")

    wechat_appid: str = Field(..., alias="WECHAT_APPID")
    wechat_secret: str = Field(..., alias="WECHAT_SECRET")
    wechat_api_base: str = Field("https://api.weixin.qq.com", alias="WECHAT_API_BASE")
    wechat_timeout_seconds: float = Field(5.0, alias="WECHAT_TIMEOUT_SECONDS")

    default_timezone: str = Field("Asia/Shanghai", alias="DEFAULT_TIMEZONE")
    father_customer_morning_quota: int = Field(2, alias="FATHER_CUSTOMER_MORNING_QUOTA")
    father_customer_afternoon_quota: int = Field(2, alias="FATHER_CUSTOMER_AFTERNOON_QUOTA")


@lru_cache(1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()


settings = get_settings()
