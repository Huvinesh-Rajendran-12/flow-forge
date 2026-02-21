from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings


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

    # ------------------------------------------------------------------
    # Connector mode
    # ------------------------------------------------------------------
    # "simulator" — always use in-memory simulators (default, no external calls)
    # "hybrid"    — use real connector per service when credentials are set,
    #               fall back to simulator when not
    # "real"      — same routing as hybrid; signals intent to use real services
    connector_mode: Literal["simulator", "hybrid", "real"] = "simulator"

    # ------------------------------------------------------------------
    # Slack credentials
    # ------------------------------------------------------------------
    slack_bot_token: Optional[str] = None   # xoxb-...

    # ------------------------------------------------------------------
    # GitHub credentials
    # ------------------------------------------------------------------
    github_token: Optional[str] = None      # ghp_... or GitHub App installation token
    github_org: Optional[str] = None        # default org name

    # ------------------------------------------------------------------
    # Jira credentials (Jira Cloud REST API v3)
    # ------------------------------------------------------------------
    jira_base_url: Optional[str] = None     # https://yourorg.atlassian.net
    jira_email: Optional[str] = None        # user@yourorg.com
    jira_api_token: Optional[str] = None    # Atlassian API token
    jira_project_key: Optional[str] = None  # e.g. "ONBOARD"

    # ------------------------------------------------------------------
    # Google Workspace credentials (service account with domain-wide delegation)
    # ------------------------------------------------------------------
    google_service_account_json: Optional[str] = None  # full JSON string of service account key
    google_admin_email: Optional[str] = None            # admin@yourdomain.com (delegated user)
    google_domain: Optional[str] = None                 # yourdomain.com

    # ------------------------------------------------------------------
    # HR system (generic configurable REST webhook)
    # ------------------------------------------------------------------
    hr_base_url: Optional[str] = None       # https://hr.internal/api
    hr_api_key: Optional[str] = None        # Bearer token

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
