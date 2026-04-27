from dataclasses import dataclass

import pytest
from flask import Flask

from access.app.runtime_permissions import RuntimePermissionProvider


@dataclass(slots=True)
class RuntimeSettings:
    owner_can_view_category_tree: bool = False
    owner_can_edit_taxonomy: bool = False
    owner_can_view_products: bool = False
    owner_can_edit_products: bool = False
    owner_can_create_demo_data: bool = False


class SettingsRepo:
    def __init__(self, settings=None, *, fail: bool = False) -> None:
        self.settings = settings
        self.fail = fail
        self.calls = 0

    def get(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("settings unavailable")
        return self.settings


@pytest.mark.unit
class TestRuntimePermissionProvider:
    def test_superadmin_is_always_allowed_even_when_settings_fail(self):
        repo = SettingsRepo(fail=True)
        provider = RuntimePermissionProvider(_settings_repo=repo)

        assert provider({"role": "superadmin"}, "edit_products") is True
        assert repo.calls == 0

    def test_taxonomy_read_is_baseline_but_product_access_stays_runtime_configured(self):
        repo = SettingsRepo(
            RuntimeSettings(
                owner_can_view_category_tree=False,
                owner_can_view_products=False,
                owner_can_edit_products=True,
            )
        )
        provider = RuntimePermissionProvider(_settings_repo=repo)
        payload = {
            "role": "owner",
            "permissions": {
                "view_category_tree": False,
                "view_products": True,
                "view_orders": True,
            },
        }

        assert provider(payload, "view_category_tree") is True
        assert provider(payload, "view_products") is True
        assert provider(payload, "edit_products") is True
        assert provider(payload, "view_orders") is True

    def test_runtime_catalog_permissions_fail_closed_on_settings_errors(self):
        repo = SettingsRepo(fail=True)
        provider = RuntimePermissionProvider(_settings_repo=repo)
        payload = {
            "role": "owner",
            "permissions": {
                "view_category_tree": True,
                "view_products": True,
                "view_orders": True,
            },
        }

        assert provider(payload, "view_category_tree") is False
        assert provider(payload, "view_products") is False
        assert provider(payload, "view_orders") is True

    def test_runtime_settings_are_cached_for_one_request(self):
        app = Flask(__name__)
        repo = SettingsRepo(RuntimeSettings(owner_can_edit_products=True))
        provider = RuntimePermissionProvider(_settings_repo=repo)

        with app.test_request_context("/admin/catalog/"):
            assert provider({"role": "owner"}, "view_category_tree") is True
            assert provider({"role": "owner"}, "edit_products") is True
            assert repo.calls == 1
