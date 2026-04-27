from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateSettingsCommand:
    """
    Command to update system settings.
    All fields are optional; only provided fields will be updated.
    """

    phone: str | None = None
    email: str | None = None
    address: str | None = None
    working_hours: str | None = None
    coords_lat: float | None = None
    coords_lon: float | None = None
    instagram: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    app_name: str | None = None
    admin_panel_title: str | None = None
    owner_can_view_category_tree: bool | None = None
    owner_can_edit_taxonomy: bool | None = None
    owner_can_view_products: bool | None = None
    owner_can_edit_products: bool | None = None
    owner_can_create_demo_data: bool | None = None
