import dataclasses
import re
from dataclasses import dataclass, field

from shared.generics.errors import DomainError

# HH:MM with 00-23 hours and 00-59 minutes
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_DAYS_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_DAYS_RU = {"mon": "Пн", "tue": "Вт", "wed": "Ср", "thu": "Чт", "fri": "Пт", "sat": "Сб", "sun": "Вс"}


class InvalidCoordsError(DomainError):
    def __init__(self, field: str, value: float) -> None:
        super().__init__(
            message=f"Некорректная координата {field}: {value}",
            code="INVALID_COORDS",
        )


class InvalidScheduleError(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Некорректное расписание: {reason}",
            code="INVALID_SCHEDULE",
        )


def _validate_time(t: str, field_name: str) -> None:
    if not _TIME_RE.match(t):
        raise InvalidScheduleError(f"{field_name}='{t}' не соответствует формату HH:MM")


@dataclass(frozen=True, slots=True, kw_only=True)
class DaySchedule:
    """
    Work schedule for a single calendar day.

    Invariants:
    - opens_at and closes_at must match HH:MM (00:00–23:59).
    - opens_at < closes_at (non-empty interval).
    - If break_start is set, break_end must be set and vice-versa.
    - opens_at <= break_start < break_end <= closes_at.
    """

    opens_at: str
    closes_at: str
    break_start: str | None = None
    break_end: str | None = None

    def __post_init__(self) -> None:
        _validate_time(self.opens_at, "opens_at")
        _validate_time(self.closes_at, "closes_at")

        if self.opens_at >= self.closes_at:
            raise InvalidScheduleError(
                f"opens_at ({self.opens_at}) должно быть меньше closes_at ({self.closes_at})"
            )

        # Break consistency
        has_start = self.break_start is not None
        has_end = self.break_end is not None

        if has_start != has_end:
            raise InvalidScheduleError(
                "break_start и break_end должны быть заданы оба или оба отсутствовать"
            )

        if has_start and has_end:
            _validate_time(self.break_start, "break_start")  # type: ignore[arg-type]
            _validate_time(self.break_end, "break_end")  # type: ignore[arg-type]

            if self.break_start >= self.break_end:  # type: ignore[operator]
                raise InvalidScheduleError(
                    f"break_start ({self.break_start}) должно быть меньше break_end ({self.break_end})"
                )
            if self.break_start < self.opens_at:  # type: ignore[operator]
                raise InvalidScheduleError(
                    f"break_start ({self.break_start}) не может быть раньше opens_at ({self.opens_at})"
                )
            if self.break_end > self.closes_at:  # type: ignore[operator]
                raise InvalidScheduleError(
                    f"break_end ({self.break_end}) не может быть позже closes_at ({self.closes_at})"
                )


def _day_label(day: DaySchedule | None) -> str:
    """Render a single DaySchedule as a time-range string, or 'выходной'."""
    if day is None:
        return "выходной"
    if day.break_start is not None:
        return f"{day.opens_at}–{day.break_start}, {day.break_end}–{day.closes_at}"
    return f"{day.opens_at}–{day.closes_at}"


def _build_working_hours_text(schedule: dict[str, "DaySchedule | None"]) -> str:
    """
    Render the weekly schedule as a compact human-readable string.

    Groups consecutive days with identical schedules. Examples:
    - "Пн–Пт: 09:00–21:00; Сб: 10:00–20:00; Вс: выходной"
    - "Закрыто"  (all None)
    """
    # Build ordered list of (day_key, label)
    ordered = [(_DAYS_RU[d], _day_label(schedule.get(d))) for d in _DAYS_ORDER]

    # Group consecutive days with the same label
    groups: list[tuple[str, str, str]] = []  # (first_ru, last_ru, label)
    for ru_name, label in ordered:
        if groups and groups[-1][2] == label:
            groups[-1] = (groups[-1][0], ru_name, label)
        else:
            groups.append((ru_name, ru_name, label))

    # Check all-closed
    if all(g[2] == "выходной" for g in groups):
        return "Закрыто"

    # Render each group
    parts: list[str] = []
    for first, last, label in groups:
        day_part = first if first == last else f"{first}–{last}"
        parts.append(f"{day_part}: {label}")

    return "; ".join(parts)


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
    working_hours_schedule: dict[str, DaySchedule | None] = field(
        default_factory=lambda: {d: None for d in _DAYS_ORDER}
    )
    telegram_public_url: str = ""
    viber_url: str = ""
    whatsapp_url: str = ""
    # Stage-A shim: repo/schema still read/write this field until Stage C.
    # Remove after Stage C migrates the DB column and repo mapper.
    working_hours: str = ""

    @property
    def working_hours_text(self) -> str:
        """Human-readable schedule grouping consecutive identical days."""
        return _build_working_hours_text(self.working_hours_schedule)

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
