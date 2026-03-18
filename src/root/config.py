from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class RootConfig(BaseSettings):
    """
    Root application configuration: environment mode, CORS origins, rate limits.
    Env prefix: ROOT_

    app_env="dev"  → CORS wide open, rate limits disabled
    app_env="prod" → CORS restricted to cors_origins, strict rate limits
    """

    model_config = SettingsConfigDict(
        env_prefix="ROOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Shop Admin"
    app_env: Literal["dev", "prod"] = "dev"

    # Allowed CORS origins — used only in prod mode.
    public_cors_origins: list[str] = ["https://example.com", "https://www.example.com"]
    admin_cors_origins: list[str] = ["https://admin.example.com"]

    # Rate limits — used only in prod mode (flask-limiter format: "N per period").
    rate_limit_default: str = "200 per minute"
    rate_limit_login: str = "5 per minute"
    rate_limit_order: str = "10 per minute"
    rate_limit_recovery: str = "3 per minute"
