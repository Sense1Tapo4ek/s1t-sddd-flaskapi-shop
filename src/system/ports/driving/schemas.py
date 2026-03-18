from pydantic import BaseModel, ConfigDict, Field
from ...domain import SiteSettings
from ...app import UpdateSettingsCommand


class FetchChatIdIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    bot_token: str = Field(..., description="Telegram Bot Token to fetch updates from")


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


class SettingsOut(BaseModel):
    """Full settings view for Admin."""

    model_config = ConfigDict(frozen=True)
    contacts: ContactsOut
    telegram: TelegramOut
    coords: CoordsOut
    socials: SocialsOut

    @classmethod
    def from_domain(cls, s: SiteSettings) -> "SettingsOut":
        return cls(
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
        )


class InfoOut(BaseModel):
    """Public info view (safe, no secrets)."""

    model_config = ConfigDict(frozen=True)
    phone: str
    address: str
    email: str
    working_hours: str
    coords: CoordsOut
    socials: SocialsOut

    @classmethod
    def from_domain(cls, s: SiteSettings) -> "InfoOut":
        return cls(
            phone=s.phone,
            address=s.address,
            email=s.email,
            working_hours=s.working_hours,
            coords=CoordsOut(lat=s.coords_lat, lon=s.coords_lon),
            socials=SocialsOut(instagram=s.instagram),
        )


class SettingsUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    contacts: dict | None = Field(None, example={"phone": "+375..."})
    telegram: dict | None = Field(None, example={"bot_token": "..."})
    coords: dict | None = None
    socials: dict | None = None

    def to_command(self) -> UpdateSettingsCommand:
        kwargs: dict = {}
        if self.contacts:
            kwargs.update(self.contacts)
        if self.telegram:
            if "bot_token" in self.telegram:
                kwargs["telegram_bot_token"] = self.telegram["bot_token"]
            if "chat_id" in self.telegram:
                kwargs["telegram_chat_id"] = self.telegram["chat_id"]
        if self.coords:
            if "lat" in self.coords:
                kwargs["coords_lat"] = self.coords["lat"]
            if "lon" in self.coords:
                kwargs["coords_lon"] = self.coords["lon"]
        if self.socials:
            kwargs.update(self.socials)
        return UpdateSettingsCommand(**kwargs)
