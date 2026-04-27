import pytest

from system.domain.settings_agg import InvalidCoordsError, SiteSettings


def _settings() -> SiteSettings:
    return SiteSettings(
        id=1,
        phone="+375291234567",
        email="shop@example.com",
        address="Minsk",
        working_hours="10:00-20:00",
        coords_lat=53.9,
        coords_lon=27.56,
        instagram="",
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


@pytest.mark.unit
class TestSiteSettingsTelegramConfig:
    def test_telegram_is_configured_only_when_token_and_chat_are_present(self):
        """
        Given site settings with incomplete Telegram credentials,
        When checking Telegram configuration,
        Then both token and chat id are required.
        """
        # Arrange
        settings = _settings()

        # Act / Assert
        assert settings.is_telegram_configured is False

        # Act
        settings.telegram_bot_token = "token"
        settings.telegram_chat_id = "chat"

        # Assert
        assert settings.is_telegram_configured is True


@pytest.mark.unit
class TestSiteSettingsUpdate:
    def test_none_values_do_not_overwrite_existing_settings(self):
        """
        Given existing site settings,
        When updating a field with None,
        Then the existing value is preserved.
        """
        # Arrange
        settings = _settings()

        # Act
        settings.update(phone=None, email="new@example.com")

        # Assert
        assert settings.phone == "+375291234567"
        assert settings.email == "new@example.com"

    @pytest.mark.parametrize(
        ("field_name", "valid_value"),
        [
            ("coords_lat", -90.0),
            ("coords_lat", 90.0),
            ("coords_lon", -180.0),
            ("coords_lon", 180.0),
        ],
    )
    def test_coordinate_bounds_are_inclusive(self, field_name, valid_value):
        """
        Given a coordinate value on the valid boundary,
        When updating site settings,
        Then the boundary value is accepted.
        """
        # Arrange
        settings = _settings()

        # Act
        settings.update(**{field_name: valid_value})

        # Assert
        assert getattr(settings, field_name) == valid_value

    @pytest.mark.parametrize(
        ("field_name", "invalid_value"),
        [
            ("coords_lat", -90.1),
            ("coords_lat", 90.1),
            ("coords_lon", -180.1),
            ("coords_lon", 180.1),
        ],
    )
    def test_out_of_range_coordinate_is_rejected_without_coordinate_mutation(
        self, field_name, invalid_value
    ):
        """
        Given an out-of-range coordinate value,
        When updating site settings,
        Then the domain rejects it and keeps the previous coordinate value.
        """
        # Arrange
        settings = _settings()
        previous_value = getattr(settings, field_name)

        # Act
        with pytest.raises(InvalidCoordsError) as exc_info:
            settings.update(**{field_name: invalid_value})

        # Assert
        assert exc_info.value.code == "INVALID_COORDS"
        assert getattr(settings, field_name) == previous_value

    def test_runtime_template_and_catalog_access_settings_are_mutable(self):
        """
        Given template and catalog access settings live in SiteSettings,
        When updating them through the aggregate,
        Then the runtime values are changed without touching env config.
        """
        # Arrange
        settings = _settings()

        # Act
        settings.update(
            app_name="Runtime Shop",
            admin_panel_title="Панель магазина",
            owner_can_view_category_tree=False,
            owner_can_edit_taxonomy=True,
            owner_can_view_products=True,
            owner_can_edit_products=True,
            owner_can_create_demo_data=True,
        )

        # Assert
        assert settings.app_name == "Runtime Shop"
        assert settings.admin_panel_title == "Панель магазина"
        assert settings.owner_can_view_category_tree is True
        assert settings.owner_can_edit_taxonomy is True
        assert settings.owner_can_view_products is True
        assert settings.owner_can_edit_products is True
        assert settings.owner_can_create_demo_data is True
