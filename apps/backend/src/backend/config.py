from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Direct Anthropic API
    anthropic_api_key: Optional[str] = None

    # OpenRouter (alternative)
    openrouter_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    anthropic_auth_token: Optional[str] = None

    # Agent config
    default_model: str = "haiku"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
