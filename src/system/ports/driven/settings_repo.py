from dataclasses import dataclass
from typing import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.generics.errors import DrivenPortError
from system.adapters.driven.db.models import SettingsModel
from system.app.interfaces import ISettingsRepo
from system.domain import SiteSettings


@dataclass(frozen=True, slots=True, kw_only=True)
class SettingsRepo(ISettingsRepo):
    _session_factory: Callable[[], Session]

    def _to_domain(self, model: SettingsModel) -> SiteSettings:
        return SiteSettings(
            id=model.id,
            phone=model.phone,
            email=model.email,
            address=model.address,
            working_hours=model.working_hours,
            coords_lat=model.coords_lat,
            coords_lon=model.coords_lon,
            instagram=model.instagram,
            telegram_bot_token=model.telegram_bot_token,
            telegram_chat_id=model.telegram_chat_id,
        )

    def get(self) -> SiteSettings | None:
        try:
            with self._session_factory() as session:
                model = session.execute(
                    select(SettingsModel).where(SettingsModel.id == 1)
                ).scalar_one_or_none()

                if model is None:
                    return None
                return self._to_domain(model)
        except Exception as e:
            raise DrivenPortError(f"DB Error loading settings: {e}")

    def save(self, settings: SiteSettings) -> None:
        try:
            with self._session_factory() as session:
                # Upsert logic for Singleton
                model = session.execute(
                    select(SettingsModel).where(SettingsModel.id == 1)
                ).scalar_one_or_none()

                if model is None:
                    model = SettingsModel(id=1)
                    session.add(model)

                # Map Domain -> ORM
                model.phone = settings.phone
                model.email = settings.email
                model.address = settings.address
                model.working_hours = settings.working_hours
                model.coords_lat = settings.coords_lat
                model.coords_lon = settings.coords_lon
                model.instagram = settings.instagram
                model.telegram_bot_token = settings.telegram_bot_token
                model.telegram_chat_id = settings.telegram_chat_id

                session.commit()
        except Exception as e:
            raise DrivenPortError(f"DB Error saving settings: {e}")
