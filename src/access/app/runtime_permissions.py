from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from flask import g, has_request_context

from access.permissions import RUNTIME_CATALOG_PERMISSIONS, resolve_permissions

logger = logging.getLogger("access.permissions")


class RuntimePermissionSettings(Protocol):
    owner_can_view_category_tree: bool
    owner_can_edit_taxonomy: bool
    owner_can_view_products: bool
    owner_can_edit_products: bool
    owner_can_create_demo_data: bool


class RuntimePermissionSettingsRepo(Protocol):
    def get(self) -> RuntimePermissionSettings | None: ...


@dataclass(frozen=True, slots=True)
class RuntimePermissionConfig:
    owner_can_view_category_tree: bool
    owner_can_edit_taxonomy: bool
    owner_can_view_products: bool
    owner_can_edit_products: bool
    owner_can_create_demo_data: bool
    owner_can_view_orders: bool = False
    owner_can_manage_orders: bool = False
    owner_can_manage_settings: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimePermissionProvider:
    _settings_repo: RuntimePermissionSettingsRepo

    def __call__(self, payload: dict, permission: str) -> bool:
        if payload.get("role") == "superadmin":
            return True
        if permission not in RUNTIME_CATALOG_PERMISSIONS:
            return bool((payload.get("permissions") or {}).get(permission))

        permissions = self._runtime_permissions()
        if permissions is None:
            return False
        return bool(permissions.get(permission))

    def _runtime_permissions(self) -> dict[str, bool] | None:
        cache_key = "_access_runtime_catalog_permissions"
        if has_request_context() and hasattr(g, cache_key):
            return getattr(g, cache_key)

        try:
            settings = self._settings_repo.get()
            if settings is None:
                permissions = None
            else:
                permissions = resolve_permissions(
                    "owner",
                    RuntimePermissionConfig(
                        owner_can_view_category_tree=bool(
                            settings.owner_can_view_category_tree
                        ),
                        owner_can_edit_taxonomy=bool(settings.owner_can_edit_taxonomy),
                        owner_can_view_products=bool(settings.owner_can_view_products),
                        owner_can_edit_products=bool(settings.owner_can_edit_products),
                        owner_can_create_demo_data=bool(
                            settings.owner_can_create_demo_data
                        ),
                    ),
                )
        except Exception:
            logger.exception("Failed to resolve runtime catalog permissions")
            permissions = None

        if has_request_context():
            setattr(g, cache_key, permissions)
        return permissions
