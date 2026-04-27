import copy

import pytest

from system.app import ManageSettingsUseCase, UpdateSettingsCommand
from system.domain import SettingsNotFoundError, SiteSettings


pytestmark = pytest.mark.flow


class InMemorySettingsRepo:
    def __init__(self, settings: SiteSettings | None) -> None:
        self.settings = settings
        self.saved: list[SiteSettings] = []
        self.get_calls = 0

    def get(self) -> SiteSettings | None:
        self.get_calls += 1
        return self.settings

    def save(self, settings: SiteSettings) -> None:
        self.saved.append(copy.deepcopy(settings))
        self.settings = settings


def _settings() -> SiteSettings:
    return SiteSettings(
        id=1,
        phone="+375291234567",
        email="shop@example.com",
        address="Minsk",
        working_hours="10:00-20:00",
        coords_lat=53.9,
        coords_lon=27.56,
        instagram="@shop",
        telegram_bot_token="",
        telegram_chat_id="",
        app_name="Shop Admin",
        admin_panel_title="Админ панель",
        owner_can_view_category_tree=True,
        owner_can_edit_taxonomy=False,
        owner_can_view_products=False,
        owner_can_edit_products=False,
        owner_can_create_demo_data=False,
    )


class TestManageSettingsUseCase:
    def test_loads_applies_domain_update_and_saves(self):
        """
        Given existing site settings and a partial update command,
        When managing settings,
        Then the use case applies the domain update and saves the aggregate.
        """
        # Arrange
        settings = _settings()
        repo = InMemorySettingsRepo(settings)
        use_case = ManageSettingsUseCase(_repo=repo)

        # Act
        result = use_case(
            UpdateSettingsCommand(
                phone="+375291111111",
                email="new@example.com",
                coords_lat=54.0,
            )
        )

        # Assert
        assert result is settings
        assert repo.get_calls == 1
        assert repo.saved == [settings]
        assert repo.saved[0] is not settings
        assert settings.phone == "+375291111111"
        assert settings.email == "new@example.com"
        assert settings.coords_lat == 54.0
        assert settings.address == "Minsk"

    def test_missing_settings_raises_not_found(self):
        """
        Given the settings repo has no settings aggregate,
        When managing settings,
        Then the use case raises SettingsNotFoundError and does not save.
        """
        # Arrange
        repo = InMemorySettingsRepo(None)
        use_case = ManageSettingsUseCase(_repo=repo)

        # Act
        with pytest.raises(SettingsNotFoundError) as exc_info:
            use_case(UpdateSettingsCommand(phone="+375291111111"))

        # Assert
        assert exc_info.value.code == "SETTINGS_NOT_FOUND"
        assert repo.get_calls == 1
        assert repo.saved == []

    def test_updates_runtime_template_and_catalog_access_fields(self):
        """
        Given runtime template and catalog access fields,
        When managing settings,
        Then the use case persists those fields with the rest of SiteSettings.
        """
        # Arrange
        settings = _settings()
        repo = InMemorySettingsRepo(settings)
        use_case = ManageSettingsUseCase(_repo=repo)

        # Act
        result = use_case(
            UpdateSettingsCommand(
                app_name="Runtime Shop",
                admin_panel_title="Панель магазина",
                owner_can_view_products=True,
                owner_can_edit_products=True,
                owner_can_create_demo_data=True,
            )
        )

        # Assert
        assert result is settings
        assert repo.saved == [settings]
        assert settings.app_name == "Runtime Shop"
        assert settings.admin_panel_title == "Панель магазина"
        assert settings.owner_can_view_category_tree is True
        assert settings.owner_can_view_products is True
        assert settings.owner_can_edit_products is True
        assert settings.owner_can_create_demo_data is True
