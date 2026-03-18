from dataclasses import dataclass


@dataclass(slots=True)
class SiteSettings:
    """
    Aggregate Root for global system configuration.
    Acts as a Singleton (ID is always 1 in DB).
    """

    id: int
    phone: str
    email: str
    address: str
    working_hours: str
    coords_lat: float
    coords_lon: float
    instagram: str
    telegram_bot_token: str
    telegram_chat_id: str

    @property
    def is_telegram_configured(self) -> bool:
        """Check if Telegram integration parameters are present."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def update(
        self,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        working_hours: str | None = None,
        coords_lat: float | None = None,
        coords_lon: float | None = None,
        instagram: str | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
    ) -> None:
        """
        Apply partial updates to the aggregate.
        Only non-None values are updated.
        """
        if phone is not None:
            self.phone = phone
        if email is not None:
            self.email = email
        if address is not None:
            self.address = address
        if working_hours is not None:
            self.working_hours = working_hours
        if coords_lat is not None:
            self.coords_lat = coords_lat
        if coords_lon is not None:
            self.coords_lon = coords_lon
        if instagram is not None:
            self.instagram = instagram
        if telegram_bot_token is not None:
            self.telegram_bot_token = telegram_bot_token
        if telegram_chat_id is not None:
            self.telegram_chat_id = telegram_chat_id
