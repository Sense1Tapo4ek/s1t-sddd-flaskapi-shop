import pytest
from pydantic import ValidationError

from system.ports.driving.schemas import SettingsUpdateIn


@pytest.mark.unit
def test_settings_update_typed_booleans_parse_false_string_as_false():
    schema = SettingsUpdateIn(
        catalog_access={
            "owner_can_view_products": "false",
            "owner_can_edit_products": "true",
        }
    )

    command = schema.to_command()

    assert command.owner_can_view_products is False
    assert command.owner_can_edit_products is True


@pytest.mark.unit
def test_settings_update_typed_booleans_reject_invalid_strings():
    with pytest.raises(ValidationError):
        SettingsUpdateIn(catalog_access={"owner_can_view_products": "definitely"})
