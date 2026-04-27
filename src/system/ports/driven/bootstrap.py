from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from access.config import AccessConfig
from root.config import RootConfig
from system.adapters.driven.db.models import SettingsModel

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
                owner_can_view_category_tree=True,
                owner_can_edit_taxonomy=access_config.owner_can_edit_taxonomy,
                owner_can_view_products=access_config.owner_can_view_products,
                owner_can_edit_products=access_config.owner_can_edit_products,
                owner_can_create_demo_data=access_config.owner_can_create_demo_data,
            )
            session.add(settings)
            logger.info("Created default system settings")
        elif not settings.app_name:
            settings.app_name = root_config.app_name

        if not settings.admin_panel_title:
            settings.admin_panel_title = "Админ панель"
        settings.owner_can_view_category_tree = True
        session.commit()
