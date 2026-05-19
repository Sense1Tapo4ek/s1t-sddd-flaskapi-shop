from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateStorageSettingsCommand:
    """
    Command to update storage settings.
    All fields are optional; only provided fields will be applied.
    `secret_access_key=None` means "do not change". Pass empty string to clear.
    """

    backend: str | None = None
    endpoint_url: str | None = None
    region: str | None = None
    bucket: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    public_base_url: str | None = None
    force_path_style: bool | None = None
    test_connection: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateSettingsCommand:
    """
    Command to update system settings.
    All fields are optional; only provided fields will be updated.
    """

    phone: str | None = None
    email: str | None = None
    address: str | None = None
    working_hours_schedule: dict[str, dict | None] | None = None
    coords_lat: float | None = None
    coords_lon: float | None = None
    instagram: str | None = None
    telegram_public_url: str | None = None
    whatsapp_url: str | None = None
    viber_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    owner_can_view_category_tree: bool | None = None
    owner_can_edit_taxonomy: bool | None = None
    owner_can_view_products: bool | None = None
    owner_can_edit_products: bool | None = None
    owner_can_create_demo_data: bool | None = None
