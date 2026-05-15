import pytest

from system.domain import StorageSettings
from system.ports.driving import StorageSettingsOut, StorageSettingsUpdateIn


pytestmark = pytest.mark.unit


class TestStorageSettingsOut:
    def test_secret_is_not_serialised_even_partially(self):
        """
        Given a StorageSettings with a non-empty secret,
        When serialising for the admin UI,
        Then no field contains any portion of the secret value.
        """
        # Arrange
        settings = StorageSettings(
            id=1,
            backend="s3",
            bucket="b",
            access_key_id="AKIA",
            secret_access_key="super-very-secret-AKIASECRET1234567890",
            public_base_url="https://x",
        )

        # Act
        payload = StorageSettingsOut.from_domain(settings).model_dump()

        # Assert
        assert "secret_access_key" not in payload
        assert "secret_access_key_masked" not in payload
        assert payload["secret_access_key_set"] is True
        for value in payload.values():
            assert "AKIASECRET" not in str(value)
            assert "1234567890" not in str(value)

    def test_secret_set_flag_is_false_when_empty(self):
        """
        Given a StorageSettings with empty secret,
        When serialising,
        Then secret_access_key_set is False.
        """
        # Arrange
        settings = StorageSettings(id=1, backend="local")

        # Act
        payload = StorageSettingsOut.from_domain(settings).model_dump()

        # Assert
        assert payload["secret_access_key_set"] is False


class TestStorageSettingsUpdateIn:
    def test_to_command_passes_only_provided_fields(self):
        """
        Given a partial update schema,
        When converting to command,
        Then unset fields are None and set fields are forwarded as-is.
        """
        # Arrange
        schema = StorageSettingsUpdateIn(backend="s3", bucket="b", test_connection=True)

        # Act
        cmd = schema.to_command()

        # Assert
        assert cmd.backend == "s3"
        assert cmd.bucket == "b"
        assert cmd.secret_access_key is None
        assert cmd.endpoint_url is None
        assert cmd.test_connection is True

    def test_invalid_backend_value_is_rejected_at_schema_level(self):
        """
        Given a backend value outside the allow-list,
        When constructing the schema,
        Then Pydantic rejects it before reaching the use case.
        """
        # Act / Assert
        with pytest.raises(Exception):
            StorageSettingsUpdateIn(backend="ftp")
