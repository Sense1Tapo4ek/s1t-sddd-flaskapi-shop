from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from ...domain import DaySchedule, SiteSettings, StorageSettings, SnapshotInfo
from ...app import UpdateSettingsCommand, UpdateStorageSettingsCommand


@dataclass(frozen=True, slots=True)
class SocialsFlags:
    """Visibility flags for each social channel — mirrors SystemConfig."""

    instagram: bool = True
    telegram: bool = True
    whatsapp: bool = True
    viber: bool = True


_ALL_SOCIALS_ON = SocialsFlags()


def _build_socials(s: SiteSettings, flags: SocialsFlags) -> "SocialsOut":
    return SocialsOut(
        instagram=s.instagram if flags.instagram else None,
        telegram=s.telegram_public_url if flags.telegram else None,
        whatsapp=s.whatsapp_url if flags.whatsapp else None,
        viber=s.viber_url if flags.viber else None,
    )


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
    """
    Public social-network handles.

    Each field is independently gated by a SystemConfig.socials_*_enabled
    flag. Disabled fields are absent from the serialised payload (via
    `exclude_none=True` in the facade), so clients only see what the
    operator has chosen to expose.
    """

    model_config = ConfigDict(frozen=True)
    instagram: str | None = None
    telegram: str | None = None
    whatsapp: str | None = None
    viber: str | None = None


class DayScheduleOut(BaseModel):
    """Single day schedule for the admin form editor."""

    model_config = ConfigDict(frozen=True)
    opens_at: str
    closes_at: str
    break_start: str | None = None
    break_end: str | None = None

    @classmethod
    def from_domain(cls, ds: DaySchedule) -> "DayScheduleOut":
        return cls(
            opens_at=ds.opens_at,
            closes_at=ds.closes_at,
            break_start=ds.break_start,
            break_end=ds.break_end,
        )


def _schedule_out(s: SiteSettings) -> dict[str, "DayScheduleOut | None"]:
    return {
        day: (DayScheduleOut.from_domain(ds) if ds is not None else None)
        for day, ds in s.working_hours_schedule.items()
    }


class ContactsOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    phone: str
    email: str
    working_hours: str
    working_hours_schedule: dict[str, DayScheduleOut | None]
    address: str


class TelegramOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    bot_token: str
    chat_id: str


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
    contacts: ContactsOut
    telegram: TelegramOut
    coords: CoordsOut
    socials: SocialsOut
    catalog_access: CatalogAccessOut

    @classmethod
    def from_domain(
        cls, s: SiteSettings, socials_flags: SocialsFlags | None = None
    ) -> "SettingsOut":
        flags = socials_flags or _ALL_SOCIALS_ON
        return cls(
            contacts=ContactsOut(
                phone=s.phone,
                email=s.email,
                working_hours=s.working_hours_text,
                working_hours_schedule=_schedule_out(s),
                address=s.address,
            ),
            telegram=TelegramOut(
                bot_token=s.telegram_bot_token, chat_id=s.telegram_chat_id
            ),
            coords=CoordsOut(lat=s.coords_lat, lon=s.coords_lon),
            socials=_build_socials(s, flags),
            catalog_access=CatalogAccessOut(
                owner_can_view_category_tree=s.owner_can_view_category_tree,
                owner_can_edit_taxonomy=s.owner_can_edit_taxonomy,
                owner_can_view_products=s.owner_can_view_products,
                owner_can_edit_products=s.owner_can_edit_products,
                owner_can_create_demo_data=s.owner_can_create_demo_data,
            ),
        )


class InfoOut(BaseModel):
    """Public info view (safe, no secrets).

    ``app_name`` is supplied by the facade from ``RootConfig`` — it is an
    env-managed value, not a DB-persisted setting.
    """

    model_config = ConfigDict(frozen=True)
    phone: str
    app_name: str
    address: str
    email: str
    working_hours: str
    coords: CoordsOut
    socials: SocialsOut

    @classmethod
    def from_domain(
        cls,
        s: SiteSettings,
        *,
        app_name: str,
        socials_flags: SocialsFlags | None = None,
    ) -> "InfoOut":
        flags = socials_flags or _ALL_SOCIALS_ON
        return cls(
            app_name=app_name,
            phone=s.phone,
            address=s.address,
            email=s.email,
            working_hours=s.working_hours_text,
            coords=CoordsOut(lat=s.coords_lat, lon=s.coords_lon),
            socials=_build_socials(s, flags),
        )


class DayScheduleIn(BaseModel):
    """One row of the weekly schedule, all times HH:MM.

    Domain enforces invariants (opens < closes, break consistency); this
    schema just shapes the input.
    """

    model_config = ConfigDict(frozen=True)
    opens_at: str
    closes_at: str
    break_start: str | None = None
    break_end: str | None = None


class ContactsUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    working_hours_schedule: dict[str, DayScheduleIn | None] | None = None


class TelegramUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    bot_token: str | None = None
    chat_id: str | None = None


class CoordsUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    lat: float | None = None
    lon: float | None = None


class SocialsUpdateIn(BaseModel):
    """
    Partial update of social-network handles.

    Each field maps 1:1 to a column on `settings` and corresponds to a
    SystemConfig flag controlling its public visibility:
    - instagram        -> SYSTEM_SOCIALS_INSTAGRAM_ENABLED
    - telegram         -> SYSTEM_SOCIALS_TELEGRAM_ENABLED  (telegram_public_url)
    - whatsapp         -> SYSTEM_SOCIALS_WHATSAPP_ENABLED  (whatsapp_url)
    - viber            -> SYSTEM_SOCIALS_VIBER_ENABLED     (viber_url)
    """

    model_config = ConfigDict(frozen=True)
    instagram: str | None = None
    telegram: str | None = None
    whatsapp: str | None = None
    viber: str | None = None


class CatalogAccessUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    owner_can_view_category_tree: bool | None = None
    owner_can_edit_taxonomy: bool | None = None
    owner_can_view_products: bool | None = None
    owner_can_edit_products: bool | None = None
    owner_can_create_demo_data: bool | None = None


class SettingsUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
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
            socials = self.socials.model_dump(exclude_unset=True)
            if "instagram" in socials:
                kwargs["instagram"] = socials["instagram"]
            if "telegram" in socials:
                kwargs["telegram_public_url"] = socials["telegram"]
            if "whatsapp" in socials:
                kwargs["whatsapp_url"] = socials["whatsapp"]
            if "viber" in socials:
                kwargs["viber_url"] = socials["viber"]
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


class SnapshotOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    size_bytes: int
    created_at: datetime
    mig_version: int
    is_pre_restore: bool
    display_name: str

    @classmethod
    def from_domain(cls, info: SnapshotInfo) -> "SnapshotOut":
        return cls(
            name=info.name,
            size_bytes=info.size_bytes,
            created_at=info.created_at,
            mig_version=info.mig_version,
            is_pre_restore=info.is_pre_restore,
            display_name=info.display_name,
        )


class SnapshotListOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[SnapshotOut]

    @classmethod
    def from_domain(cls, infos: list[SnapshotInfo]) -> "SnapshotListOut":
        return cls(items=[SnapshotOut.from_domain(i) for i in infos])


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
