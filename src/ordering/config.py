from pydantic_settings import BaseSettings, SettingsConfigDict


class OrderingConfig(BaseSettings):
    """
    Configuration for Ordering Context.
    Env Prefix: ORDERING_
    """

    model_config = SettingsConfigDict(
        env_prefix="ORDERING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
