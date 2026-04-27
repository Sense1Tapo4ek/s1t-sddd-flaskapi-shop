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
    default_telegram_chat_id: str = ""
    superadmin_login: str = "superadmin"
    superadmin_password: str | None = None
    superadmin_telegram_chat_id: str = ""
    recovery_code_ttl_minutes: int = 5
    recovery_code_cooldown_seconds: int = 60
    recovery_code_max_attempts: int = 5
    recovery_code_lockout_minutes: int = 15

    owner_can_view_category_tree: bool = True
    owner_can_edit_taxonomy: bool = False
    owner_can_view_products: bool = False
    owner_can_edit_products: bool = False
    owner_can_view_orders: bool = False
    owner_can_manage_orders: bool = False
    owner_can_manage_settings: bool = False
    owner_can_create_demo_data: bool = False
