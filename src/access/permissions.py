from __future__ import annotations

from typing import Protocol


class AccessPermissionConfig(Protocol):
    owner_can_view_category_tree: bool
    owner_can_edit_taxonomy: bool
    owner_can_view_products: bool
    owner_can_edit_products: bool
    owner_can_view_orders: bool
    owner_can_manage_orders: bool
    owner_can_manage_settings: bool
    owner_can_create_demo_data: bool


PERMISSION_KEYS = (
    "view_category_tree",
    "edit_taxonomy",
    "view_products",
    "edit_products",
    "view_orders",
    "manage_orders",
    "manage_settings",
    "create_demo_data",
)

RUNTIME_CATALOG_PERMISSIONS = {
    "view_category_tree",
    "edit_taxonomy",
    "view_products",
    "edit_products",
    "create_demo_data",
}


def resolve_permissions(role: str, config: AccessPermissionConfig) -> dict[str, bool]:
    if role == "superadmin":
        return {key: True for key in PERMISSION_KEYS}

    permissions = {
        "view_category_tree": True,
        "edit_taxonomy": config.owner_can_edit_taxonomy,
        "view_products": config.owner_can_view_products,
        "edit_products": config.owner_can_edit_products,
        "view_orders": config.owner_can_view_orders,
        "manage_orders": config.owner_can_manage_orders,
        "manage_settings": config.owner_can_manage_settings,
        "create_demo_data": config.owner_can_create_demo_data,
    }
    if permissions["edit_taxonomy"]:
        permissions["view_category_tree"] = True
    if permissions["edit_products"]:
        permissions["view_products"] = True
        permissions["view_category_tree"] = True
    if permissions["manage_orders"]:
        permissions["view_orders"] = True
    if permissions["create_demo_data"]:
        permissions["view_category_tree"] = True
        permissions["edit_taxonomy"] = True
        permissions["view_products"] = True
        permissions["edit_products"] = True
    return permissions
