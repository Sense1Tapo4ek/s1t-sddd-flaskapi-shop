from pydantic_settings import BaseSettings, SettingsConfigDict


class SystemConfig(BaseSettings):
    """
    Configuration for System Context.
    Env Prefix: SYSTEM_
    """

    model_config = SettingsConfigDict(
        env_prefix="SYSTEM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    recovery_token: str = "default-change-me"
