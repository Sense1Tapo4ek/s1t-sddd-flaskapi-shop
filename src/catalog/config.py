from pydantic_settings import BaseSettings, SettingsConfigDict


class CatalogConfig(BaseSettings):
    """
    Configuration for Catalog Context.
    Env Prefix: CATALOG_
    """

    model_config = SettingsConfigDict(
        env_prefix="CATALOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    upload_dir: str = "media/products"
