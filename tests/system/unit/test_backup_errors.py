import pytest

from shared.generics.errors import DomainError
from system.domain.backup_errors import (
    InsufficientDiskSpaceError,
    SnapshotNameInvalidError,
    SnapshotNotFoundError,
)


@pytest.mark.unit
class TestSnapshotNotFoundError:
    def test_inherits_domain_error(self) -> None:
        err = SnapshotNotFoundError(name="snap.sql.gz")
        assert isinstance(err, DomainError)

    def test_code_is_snapshot_not_found(self) -> None:
        err = SnapshotNotFoundError(name="snap.sql.gz")
        assert err.code == "SNAPSHOT_NOT_FOUND"

    def test_name_attribute_stored(self) -> None:
        err = SnapshotNotFoundError(name="snap.sql.gz")
        assert err.name == "snap.sql.gz"

    def test_message_contains_name(self) -> None:
        err = SnapshotNotFoundError(name="snap.sql.gz")
        assert "snap.sql.gz" in err.message


@pytest.mark.unit
class TestSnapshotNameInvalidError:
    def test_inherits_domain_error(self) -> None:
        err = SnapshotNameInvalidError(name="bad/name", reason="содержит слэш")
        assert isinstance(err, DomainError)

    def test_code_is_snapshot_name_invalid(self) -> None:
        err = SnapshotNameInvalidError(name="bad/name", reason="содержит слэш")
        assert err.code == "SNAPSHOT_NAME_INVALID"

    def test_name_attribute_stored(self) -> None:
        err = SnapshotNameInvalidError(name="bad/name", reason="содержит слэш")
        assert err.name == "bad/name"

    def test_reason_attribute_stored(self) -> None:
        err = SnapshotNameInvalidError(name="bad/name", reason="содержит слэш")
        assert err.reason == "содержит слэш"

    def test_message_contains_name_and_reason(self) -> None:
        err = SnapshotNameInvalidError(name="bad/name", reason="содержит слэш")
        assert "bad/name" in err.message
        assert "содержит слэш" in err.message


@pytest.mark.unit
class TestInsufficientDiskSpaceError:
    def test_inherits_domain_error(self) -> None:
        err = InsufficientDiskSpaceError(required_bytes=1000, available_bytes=500)
        assert isinstance(err, DomainError)

    def test_code_is_insufficient_disk_space(self) -> None:
        err = InsufficientDiskSpaceError(required_bytes=1000, available_bytes=500)
        assert err.code == "INSUFFICIENT_DISK_SPACE"

    def test_required_bytes_stored(self) -> None:
        err = InsufficientDiskSpaceError(required_bytes=1000, available_bytes=500)
        assert err.required_bytes == 1000

    def test_available_bytes_stored(self) -> None:
        err = InsufficientDiskSpaceError(required_bytes=1000, available_bytes=500)
        assert err.available_bytes == 500

    def test_message_contains_both_values(self) -> None:
        err = InsufficientDiskSpaceError(required_bytes=1000, available_bytes=500)
        assert "1000" in err.message
        assert "500" in err.message
