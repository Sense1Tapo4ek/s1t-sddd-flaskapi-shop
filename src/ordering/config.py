from pydantic_settings import BaseSettings, SettingsConfigDict


class OrderingConfig(BaseSettings):
    """
    Configuration for Ordering Context.
    Env Prefix: ORDERING_

    Flags:
    - orders_enabled: master switch for the Order aggregate. When False,
      the `/orders*` public + admin endpoints are NOT registered, CORS
      and rate-limit for them are skipped, and the admin UI hides the
      Orders tab + nav entry. Inquiries (`/inquiries*`) remain unaffected.
      Default True preserves historical behaviour.
    """

    model_config = SettingsConfigDict(
        env_prefix="ORDERING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    orders_enabled: bool = True
