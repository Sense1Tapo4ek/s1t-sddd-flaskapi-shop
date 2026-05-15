import dataclasses

import pytest

from system.domain import (
    IncompleteS3SettingsError,
    InvalidStorageBackendError,
    StorageSettings,
)


pytestmark = pytest.mark.unit


def _filled_s3() -> StorageSettings:
    return StorageSettings(
        id=1,
        backend="s3",
        endpoint_url="https://s3.amazonaws.com",
        region="us-east-1",
        bucket="my-bucket",
        access_key_id="AKIA",
        secret_access_key="secret",
        public_base_url="https://my-bucket.s3.amazonaws.com",
        force_path_style=False,
    )


class TestStorageSettingsClassVar:
    def test_required_fields_constant_is_classvar_not_dataclass_field(self):
        """
        Given StorageSettings is a slots dataclass,
        When introspecting its fields,
        Then the internal _S3_REQUIRED constant must NOT appear as a per-instance field.
        """
        # Arrange / Act
        field_names = {f.name for f in dataclasses.fields(StorageSettings)}

        # Assert
        assert "_S3_REQUIRED" not in field_names

    def test_asdict_does_not_serialise_internal_constant(self):
        """
        Given a StorageSettings instance,
        When converting it via dataclasses.asdict,
        Then the output does not contain the internal required-fields constant.
        """
        # Arrange
        settings = StorageSettings(id=1, backend="local")

        # Act
        payload = dataclasses.asdict(settings)

        # Assert
        assert "_S3_REQUIRED" not in payload


class TestStorageSettingsUpdate:
    def test_none_values_do_not_overwrite_existing(self):
        """
        Given existing storage settings,
        When updating with None,
        Then the previous value is preserved.
        """
        # Arrange
        settings = _filled_s3()

        # Act
        settings.update(secret_access_key=None, bucket="other")

        # Assert
        assert settings.secret_access_key == "secret"
        assert settings.bucket == "other"

    def test_unknown_backend_value_is_rejected(self):
        """
        Given an update payload with an unsupported backend,
        When applying it,
        Then InvalidStorageBackendError is raised and state is preserved.
        """
        # Arrange
        settings = StorageSettings(id=1, backend="local")

        # Act / Assert
        with pytest.raises(InvalidStorageBackendError):
            settings.update(backend="ftp")
        assert settings.backend == "local"

    def test_empty_secret_clears_existing(self):
        """
        Given an existing secret,
        When updating secret_access_key to empty string,
        Then the secret is cleared (empty string is a real value, not None).
        """
        # Arrange
        settings = _filled_s3()

        # Act
        settings.update(secret_access_key="")

        # Assert
        assert settings.secret_access_key == ""


class TestStorageSettingsInvariant:
    def test_local_backend_skips_s3_required_check(self):
        """
        Given backend is local,
        When validating active backend,
        Then no exception is raised even if S3 fields are empty.
        """
        # Arrange
        settings = StorageSettings(id=1, backend="local")

        # Act / Assert
        settings.validate_active_backend()

    def test_s3_backend_with_all_required_fields_passes(self):
        """
        Given backend is s3 and all required fields are filled,
        When validating,
        Then no exception is raised.
        """
        # Arrange
        settings = _filled_s3()

        # Act / Assert
        settings.validate_active_backend()

    @pytest.mark.parametrize(
        ("missing_field", "expected_in_error"),
        [
            ("bucket", "bucket"),
            ("access_key_id", "access_key_id"),
            ("secret_access_key", "secret_access_key"),
            ("public_base_url", "public_base_url"),
        ],
    )
    def test_s3_backend_with_missing_field_raises(self, missing_field, expected_in_error):
        """
        Given backend is s3 but a required field is empty,
        When validating,
        Then IncompleteS3SettingsError lists the missing field.
        """
        # Arrange
        settings = _filled_s3()
        setattr(settings, missing_field, "")

        # Act / Assert
        with pytest.raises(IncompleteS3SettingsError) as exc_info:
            settings.validate_active_backend()
        assert expected_in_error in exc_info.value.missing


class TestStorageSettingsIsS3:
    def test_is_s3_returns_true_only_for_s3_backend(self):
        """
        Given two settings instances,
        When checking is_s3 property,
        Then it reflects the backend value.
        """
        # Assert
        assert StorageSettings(id=1, backend="local").is_s3 is False
        assert StorageSettings(id=1, backend="s3").is_s3 is True
