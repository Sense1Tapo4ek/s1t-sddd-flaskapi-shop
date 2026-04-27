from dataclasses import dataclass
from typing import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.helpers.db import handle_db_errors
from system.adapters.driven.db.models import SettingsModel
from system.app.interfaces import ISettingsRepo
from system.domain import SiteSettings


@dataclass(frozen=True, slots=True, kw_only=True)
class SettingsRepo(ISettingsRepo):
    _session_factory: Callable[[], Session]

    def _to_domain(self, model: SettingsModel) -> SiteSettings:
        return SiteSettings(
            id=model.id, phone=model.phone, email=model.email,
            address=model.address, working_hours=model.working_hours,
            coords_lat=model.coords_lat, coords_lon=model.coords_lon,
            instagram=model.instagram,
            telegram_bot_token=model.telegram_bot_token,
            telegram_chat_id=model.telegram_chat_id,
            app_name=model.app_name or "Shop Admin",
            admin_panel_title=model.admin_panel_title or "Админ панель",
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
            model.working_hours = settings.working_hours
            model.coords_lat = settings.coords_lat
            model.coords_lon = settings.coords_lon
            model.instagram = settings.instagram
            model.telegram_bot_token = settings.telegram_bot_token
            model.telegram_chat_id = settings.telegram_chat_id
            model.app_name = settings.app_name
            model.admin_panel_title = settings.admin_panel_title
            model.owner_can_view_category_tree = settings.owner_can_view_category_tree
            model.owner_can_edit_taxonomy = settings.owner_can_edit_taxonomy
            model.owner_can_view_products = settings.owner_can_view_products
            model.owner_can_edit_products = settings.owner_can_edit_products
            model.owner_can_create_demo_data = settings.owner_can_create_demo_data
            session.commit()
