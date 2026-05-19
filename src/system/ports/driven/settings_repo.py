import dataclasses
import json
from dataclasses import dataclass
from typing import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.helpers.db import handle_db_errors
from system.adapters.driven.db.models import SettingsModel
from system.app.interfaces import ISettingsRepo
from system.domain import DaySchedule, SiteSettings

_DAYS_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _schedule_from_json(raw: str) -> dict[str, DaySchedule | None]:
    """Deserialize the stored JSON blob into a {day: DaySchedule|None} map.

    Empty / malformed payload yields an all-closed schedule — UI can then
    re-fill it.
    """
    result: dict[str, DaySchedule | None] = {d: None for d in _DAYS_ORDER}
    if not raw:
        return result
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return result
    if not isinstance(data, dict):
        return result
    for day in _DAYS_ORDER:
        value = data.get(day)
        if value is None:
            result[day] = None
        elif isinstance(value, dict):
            try:
                result[day] = DaySchedule(**value)
            except Exception:
                result[day] = None
    return result


def _schedule_to_json(schedule: dict[str, DaySchedule | None]) -> str:
    payload: dict[str, dict | None] = {}
    for day in _DAYS_ORDER:
        ds = schedule.get(day)
        payload[day] = dataclasses.asdict(ds) if ds is not None else None
    return json.dumps(payload, ensure_ascii=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class SettingsRepo(ISettingsRepo):
    _session_factory: Callable[[], Session]

    def _to_domain(self, model: SettingsModel) -> SiteSettings:
        return SiteSettings(
            id=model.id, phone=model.phone, email=model.email,
            address=model.address,
            working_hours_schedule=_schedule_from_json(model.working_hours_schedule),
            coords_lat=model.coords_lat, coords_lon=model.coords_lon,
            instagram=model.instagram,
            telegram_public_url=model.telegram_public_url,
            whatsapp_url=model.whatsapp_url,
            viber_url=model.viber_url,
            telegram_bot_token=model.telegram_bot_token,
            telegram_chat_id=model.telegram_chat_id,
            owner_can_view_category_tree=bool(model.owner_can_view_category_tree),
            owner_can_edit_taxonomy=bool(model.owner_can_edit_taxonomy),
            owner_can_view_products=bool(model.owner_can_view_products),
            owner_can_edit_products=bool(model.owner_can_edit_products),
            owner_can_create_demo_data=bool(model.owner_can_create_demo_data),
        )

    @handle_db_errors("load settings")
    def get(self) -> SiteSettings | None:
        with self._session_factory() as session:
            model = session.execute(
                select(SettingsModel).where(SettingsModel.id == 1)
            ).scalar_one_or_none()
            return self._to_domain(model) if model else None

    @handle_db_errors("save settings")
    def save(self, settings: SiteSettings) -> None:
        with self._session_factory() as session:
            model = session.execute(
                select(SettingsModel).where(SettingsModel.id == 1)
            ).scalar_one_or_none()
            if model is None:
                model = SettingsModel(id=1)
                session.add(model)
            model.phone = settings.phone
            model.email = settings.email
            model.address = settings.address
            model.working_hours_schedule = _schedule_to_json(
                settings.working_hours_schedule
            )
            model.coords_lat = settings.coords_lat
            model.coords_lon = settings.coords_lon
            model.instagram = settings.instagram
            model.telegram_public_url = settings.telegram_public_url
            model.whatsapp_url = settings.whatsapp_url
            model.viber_url = settings.viber_url
            model.telegram_bot_token = settings.telegram_bot_token
            model.telegram_chat_id = settings.telegram_chat_id
            model.owner_can_view_category_tree = settings.owner_can_view_category_tree
            model.owner_can_edit_taxonomy = settings.owner_can_edit_taxonomy
            model.owner_can_view_products = settings.owner_can_view_products
            model.owner_can_edit_products = settings.owner_can_edit_products
            model.owner_can_create_demo_data = settings.owner_can_create_demo_data
            session.commit()
