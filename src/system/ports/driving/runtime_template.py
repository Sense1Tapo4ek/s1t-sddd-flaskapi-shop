from __future__ import annotations

import logging

from flask import g, has_request_context

from ordering.config import OrderingConfig
from root.config import RootConfig
from system.config import SystemConfig
from system.ports.driving.facade import SystemFacade

logger = logging.getLogger("system.runtime_template")


def runtime_template_settings(
    facade: SystemFacade,
    root_config: RootConfig,
    ordering_config: OrderingConfig | None = None,
    system_config: SystemConfig | None = None,
) -> dict[str, object]:
    """
    Build the per-request context dict injected into every Jinja template.

    Carries the dynamic branding plus the feature-flags both the admin nav
    and the store-form template rely on (see
    docs/subsystems/feature-flags.md).
    """
    cache_key = "_system_runtime_template_settings"
    if has_request_context() and hasattr(g, cache_key):
        return getattr(g, cache_key)

    sys_cfg = system_config if system_config is not None else facade.get_config()
    ord_cfg = ordering_config if ordering_config is not None else OrderingConfig()
    feature_flags = {
        "orders_enabled": ord_cfg.orders_enabled,
        "socials_instagram_enabled": sys_cfg.socials_instagram_enabled,
        "socials_telegram_enabled": sys_cfg.socials_telegram_enabled,
        "socials_whatsapp_enabled": sys_cfg.socials_whatsapp_enabled,
        "socials_viber_enabled": sys_cfg.socials_viber_enabled,
    }

    try:
        settings = facade.get_settings()
        values: dict[str, object] = {
            "app_name": settings.branding.app_name or root_config.app_name,
            "admin_panel_title": settings.branding.admin_panel_title or "Админ панель",
            "feature_flags": feature_flags,
        }
    except Exception:
        logger.exception("Failed to load runtime template settings")
        values = {
            "app_name": root_config.app_name,
            "admin_panel_title": "Админ панель",
            "feature_flags": feature_flags,
        }

    if has_request_context():
        setattr(g, cache_key, values)
    return values
