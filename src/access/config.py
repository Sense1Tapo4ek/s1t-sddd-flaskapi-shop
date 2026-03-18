from pydantic_settings import BaseSettings, SettingsConfigDict


class AccessConfig(BaseSettings):
    """
    Configuration for Access Context.
    Env Prefix: ACCESS_
    """

    model_config = SettingsConfigDict(
        env_prefix="ACCESS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    jwt_secret: str = "change-me-in-production"
    default_login: str = "admin"
    default_password: str = "changeme"
