from pydantic_settings import BaseSettings, SettingsConfigDict


class InfraConfig(BaseSettings):
    """
    Shared infrastructure configuration (DB, etc).
    Env Prefix: INFRA_
    """

    model_config = SettingsConfigDict(
        env_prefix="INFRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///data/shop.db"
