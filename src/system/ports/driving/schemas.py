from pydantic import BaseModel, ConfigDict, Field
from ...domain import SiteSettings, StorageSettings
from ...app import UpdateSettingsCommand, UpdateStorageSettingsCommand


class FetchChatIdIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    bot_token: str = Field(..., description="Токен бота Telegram для получения обновлений")


class TelegramChatIdOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    success: bool = True
    chat_id: str


class CoordsOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    lat: float
    lon: float


class SocialsOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    instagram: str


class ContactsOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    phone: str
    email: str
    working_hours: str
    address: str


class TelegramOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    bot_token: str
    chat_id: str


class BrandingOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    app_name: str
    admin_panel_title: str


class CatalogAccessOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    owner_can_view_category_tree: bool
    owner_can_edit_taxonomy: bool
    owner_can_view_products: bool
    owner_can_edit_products: bool
    owner_can_create_demo_data: bool


class SettingsOut(BaseModel):
    """Full settings view for Admin."""

    model_config = ConfigDict(frozen=True)
    branding: BrandingOut
    contacts: ContactsOut
    telegram: TelegramOut
    coords: CoordsOut
    socials: SocialsOut
    catalog_access: CatalogAccessOut

    @classmethod
    def from_domain(cls, s: SiteSettings) -> "SettingsOut":
        return cls(
            branding=BrandingOut(
                app_name=s.app_name,
                admin_panel_title=s.admin_panel_title,
            ),
            contacts=ContactsOut(
                phone=s.phone,
                email=s.email,
                working_hours=s.working_hours,
                address=s.address,
            ),
            telegram=TelegramOut(
                bot_token=s.telegram_bot_token, chat_id=s.telegram_chat_id
            ),
            coords=CoordsOut(lat=s.coords_lat, lon=s.coords_lon),
            socials=SocialsOut(instagram=s.instagram),
            catalog_access=CatalogAccessOut(
                owner_can_view_category_tree=s.owner_can_view_category_tree,
                owner_can_edit_taxonomy=s.owner_can_edit_taxonomy,
                owner_can_view_products=s.owner_can_view_products,
                owner_can_edit_products=s.owner_can_edit_products,
                owner_can_create_demo_data=s.owner_can_create_demo_data,
            ),
        )


class InfoOut(BaseModel):
    """Public info view (safe, no secrets)."""

    model_config = ConfigDict(frozen=True)
    phone: str
    app_name: str
    address: str
    email: str
    working_hours: str
    coords: CoordsOut
    socials: SocialsOut

    @classmethod
    def from_domain(cls, s: SiteSettings) -> "InfoOut":
        return cls(
            app_name=s.app_name,
            phone=s.phone,
            address=s.address,
            email=s.email,
            working_hours=s.working_hours,
            coords=CoordsOut(lat=s.coords_lat, lon=s.coords_lon),
            socials=SocialsOut(instagram=s.instagram),
        )


class BrandingUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    app_name: str | None = None
    admin_panel_title: str | None = None


class ContactsUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    working_hours: str | None = None


class TelegramUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    bot_token: str | None = None
    chat_id: str | None = None


class CoordsUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    lat: float | None = None
    lon: float | None = None


class SocialsUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    instagram: str | None = None


class CatalogAccessUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    owner_can_view_category_tree: bool | None = None
    owner_can_edit_taxonomy: bool | None = None
    owner_can_view_products: bool | None = None
    owner_can_edit_products: bool | None = None
    owner_can_create_demo_data: bool | None = None


class SettingsUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    branding: BrandingUpdateIn | None = None
    contacts: ContactsUpdateIn | None = Field(
        None,
        json_schema_extra={"example": {"phone": "+375..."}},
    )
    telegram: TelegramUpdateIn | None = Field(
        None,
        json_schema_extra={"example": {"bot_token": "..."}},
    )
    coords: CoordsUpdateIn | None = None
    socials: SocialsUpdateIn | None = None
    catalog_access: CatalogAccessUpdateIn | None = None

    def to_command(self) -> UpdateSettingsCommand:
        kwargs: dict = {}
        if self.branding is not None:
            kwargs.update(self.branding.model_dump(exclude_unset=True))
        if self.contacts is not None:
            kwargs.update(self.contacts.model_dump(exclude_unset=True))
        if self.telegram is not None:
            telegram = self.telegram.model_dump(exclude_unset=True)
            if "bot_token" in telegram:
                kwargs["telegram_bot_token"] = telegram["bot_token"]
            if "chat_id" in telegram:
                kwargs["telegram_chat_id"] = telegram["chat_id"]
        if self.coords is not None:
            coords = self.coords.model_dump(exclude_unset=True)
            if "lat" in coords:
                kwargs["coords_lat"] = coords["lat"]
            if "lon" in coords:
                kwargs["coords_lon"] = coords["lon"]
        if self.socials is not None:
            kwargs.update(self.socials.model_dump(exclude_unset=True))
        if self.catalog_access is not None:
            kwargs.update(self.catalog_access.model_dump(exclude_unset=True))
        return UpdateSettingsCommand(**kwargs)


class StorageSettingsOut(BaseModel):
    """
    Storage configuration for the admin UI.

    `secret_access_key` is NEVER returned, masked or otherwise — only a
    boolean flag indicating whether a secret is currently stored.
    """

    model_config = ConfigDict(frozen=True)
    backend: str
    endpoint_url: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key_set: bool
    public_base_url: str
    force_path_style: bool

    @classmethod
    def from_domain(cls, s: StorageSettings) -> "StorageSettingsOut":
        return cls(
            backend=s.backend,
            endpoint_url=s.endpoint_url,
            region=s.region,
            bucket=s.bucket,
            access_key_id=s.access_key_id,
            secret_access_key_set=bool(s.secret_access_key),
            public_base_url=s.public_base_url,
            force_path_style=s.force_path_style,
        )


class StorageSettingsUpdateIn(BaseModel):
    """
    Partial update payload. Omitted fields are kept as-is.
    `secret_access_key=None` (or absent) keeps the stored value.
    Pass an empty string to clear it.
    """

    model_config = ConfigDict(frozen=True)
    backend: str | None = Field(None, pattern="^(local|s3)$")
    endpoint_url: str | None = None
    region: str | None = None
    bucket: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    public_base_url: str | None = None
    force_path_style: bool | None = None
    test_connection: bool = False

    def to_command(self) -> UpdateStorageSettingsCommand:
        return UpdateStorageSettingsCommand(**self.model_dump())
