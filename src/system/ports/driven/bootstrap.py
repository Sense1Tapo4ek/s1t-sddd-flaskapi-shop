from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from access.config import AccessConfig
from root.config import RootConfig
from system.adapters.driven.db.models import SettingsModel, StorageSettingsModel

logger = logging.getLogger("system.bootstrap")


def bootstrap_system_defaults(
    session_factory: Callable[[], Session],
    *,
    access_config: AccessConfig,
    root_config: RootConfig,
) -> None:
    with session_factory() as session:
        settings = session.execute(
            select(SettingsModel).where(SettingsModel.id == 1)
        ).scalar_one_or_none()
        if not settings:
            settings = SettingsModel(
                id=1,
                app_name=root_config.app_name,
                admin_panel_title="Админ панель",
            )
            session.add(settings)
            logger.info("Created default system settings")
        elif not settings.app_name:
            settings.app_name = root_config.app_name

        if not settings.admin_panel_title:
            settings.admin_panel_title = "Админ панель"

        # Owner permissions: .env is the source of truth. Re-assert on every
        # boot so editing ACCESS_OWNER_CAN_* in .env propagates after restart
        # (the UI no longer exposes these fields).
        settings.owner_can_view_category_tree = True
        settings.owner_can_edit_taxonomy = access_config.owner_can_edit_taxonomy
        settings.owner_can_view_products = access_config.owner_can_view_products
        settings.owner_can_edit_products = access_config.owner_can_edit_products
        settings.owner_can_create_demo_data = access_config.owner_can_create_demo_data
        session.commit()


def bootstrap_storage_defaults(session_factory: Callable[[], Session]) -> None:
    """
    Ensure a singleton row exists in `storage_settings` with backend='local'.
    Only the very first deploy needs this — subsequent runs are no-ops.
    Switching backend and filling S3 credentials happens via the admin UI.
    """
    with session_factory() as session:
        row = session.execute(
            select(StorageSettingsModel).where(StorageSettingsModel.id == 1)
        ).scalar_one_or_none()
        if row is None:
            session.add(StorageSettingsModel(id=1, backend="local"))
            session.commit()
            logger.info("Created default storage settings (backend=local)")
