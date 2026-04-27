from dataclasses import dataclass

import pytest

from access.permissions import PERMISSION_KEYS, resolve_permissions


@dataclass(slots=True)
class PermissionConfig:
    owner_can_view_category_tree: bool = False
    owner_can_edit_taxonomy: bool = False
    owner_can_view_products: bool = False
    owner_can_edit_products: bool = False
    owner_can_view_orders: bool = False
    owner_can_manage_orders: bool = False
    owner_can_manage_settings: bool = False
    owner_can_create_demo_data: bool = False


@pytest.mark.unit
class TestSuperadminPermissions:
    def test_superadmin_gets_every_permission(self):
        """
        Given all owner permissions are disabled,
        When resolving permissions for a superadmin,
        Then every permission is granted.
        """
        # Arrange
        config = PermissionConfig()

        # Act
        permissions = resolve_permissions("superadmin", config)

        # Assert
        assert permissions == {key: True for key in PERMISSION_KEYS}


@pytest.mark.unit
class TestOwnerPermissionImplications:
    def test_owner_without_flags_gets_taxonomy_read_baseline(self):
        """
        Given all owner permission flags are disabled,
        When resolving permissions for an owner,
        Then taxonomy structure read access is still granted as the admin baseline.
        """
        # Arrange
        config = PermissionConfig()

        # Act
        permissions = resolve_permissions("owner", config)

        # Assert
        assert permissions == {
            **{key: False for key in PERMISSION_KEYS},
            "view_category_tree": True,
        }

    @pytest.mark.parametrize(
        ("enabled_flag", "implied_permissions"),
        [
            ("owner_can_edit_taxonomy", {"edit_taxonomy", "view_category_tree"}),
            (
                "owner_can_edit_products",
                {"edit_products", "view_products", "view_category_tree"},
            ),
            (
                "owner_can_manage_orders",
                {"manage_orders", "view_orders", "view_category_tree"},
            ),
            (
                "owner_can_create_demo_data",
                {
                    "create_demo_data",
                    "view_category_tree",
                    "edit_taxonomy",
                    "view_products",
                    "edit_products",
                },
            ),
        ],
    )
    def test_edit_and_manage_permissions_imply_required_read_permissions(
        self, enabled_flag, implied_permissions
    ):
        """
        Given an owner has a write/manage permission flag,
        When resolving permissions,
        Then the required read and dependency permissions are also granted.
        """
        # Arrange
        config = PermissionConfig(**{enabled_flag: True})

        # Act
        permissions = resolve_permissions("owner", config)

        # Assert
        granted_permissions = {
            key for key, is_granted in permissions.items() if is_granted
        }
        assert granted_permissions == implied_permissions
