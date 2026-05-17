from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMTP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    from_addr: str = "noreply@shop.local"
    use_tls: bool = True
    timeout: int = 10


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

    database_url: str = (
        "mysql+pymysql://shop:shop@localhost:3306/shop?charset=utf8mb4"
    )
    db_pool_size: int = 5
    db_pool_recycle: int = 3600
    db_pool_pre_ping: bool = True
