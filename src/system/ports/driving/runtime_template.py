from __future__ import annotations

import logging

from flask import g, has_request_context

from root.config import RootConfig
from system.ports.driving.facade import SystemFacade

logger = logging.getLogger("system.runtime_template")


def runtime_template_settings(
    facade: SystemFacade,
    root_config: RootConfig,
) -> dict[str, str]:
    cache_key = "_system_runtime_template_settings"
    if has_request_context() and hasattr(g, cache_key):
        return getattr(g, cache_key)

    try:
        settings = facade.get_settings()
        values = {
            "app_name": settings.branding.app_name or root_config.app_name,
            "admin_panel_title": settings.branding.admin_panel_title or "Админ панель",
        }
    except Exception:
        logger.exception("Failed to load runtime template settings")
        values = {
            "app_name": root_config.app_name,
            "admin_panel_title": "Админ панель",
        }

    if has_request_context():
        setattr(g, cache_key, values)
    return values
