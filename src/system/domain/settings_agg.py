from dataclasses import dataclass

from shared.generics.errors import DomainError


class InvalidCoordsError(DomainError):
    def __init__(self, field: str, value: float) -> None:
        super().__init__(
            message=f"Некорректная координата {field}: {value}",
            code="INVALID_COORDS",
        )


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
    app_name: str = "Shop Admin"
    admin_panel_title: str = "Админ панель"
    owner_can_view_category_tree: bool = True
    owner_can_edit_taxonomy: bool = False
    owner_can_view_products: bool = False
    owner_can_edit_products: bool = False
    owner_can_create_demo_data: bool = False

    @property
    def is_telegram_configured(self) -> bool:
        """Check if Telegram integration parameters are present."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    _COORD_BOUNDS = {"coords_lat": (-90.0, 90.0), "coords_lon": (-180.0, 180.0)}

    def update(self, **kwargs) -> None:
        """Apply partial updates. Only non-None values are set."""
        for key, val in kwargs.items():
            if val is None:
                continue
            if key in self._COORD_BOUNDS:
                lo, hi = self._COORD_BOUNDS[key]
                if not (lo <= val <= hi):
                    raise InvalidCoordsError(key.split("_")[1], val)
            setattr(self, key, val)
        self._normalize_catalog_access()

    def _normalize_catalog_access(self) -> None:
        self.owner_can_view_category_tree = True
        if self.owner_can_create_demo_data:
            self.owner_can_edit_taxonomy = True
            self.owner_can_view_products = True
            self.owner_can_edit_products = True
        if self.owner_can_edit_taxonomy:
            self.owner_can_view_category_tree = True
        if self.owner_can_edit_products:
            self.owner_can_view_products = True
