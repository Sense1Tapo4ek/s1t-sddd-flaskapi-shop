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
    # Fernet key (URL-safe base64, 32 bytes). Used to encrypt secret_access_key
    # in the storage_settings table. Generate via:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    storage_secrets_key: str = ""
