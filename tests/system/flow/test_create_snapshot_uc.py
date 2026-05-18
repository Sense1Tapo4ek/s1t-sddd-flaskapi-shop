"""
Flow tests for CreateSnapshotUseCase.

Fakes replace ISnapshotStorage and IBackupRunner — no real filesystem or DB.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest

from system.domain import SnapshotInfo

pytestmark = pytest.mark.flow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_info(name: str) -> SnapshotInfo:
    return SnapshotInfo(
        name=name,
        size_bytes=1024,
        created_at=datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc),
        mig_version=7,
        is_pre_restore="pre-restore-" in name,
    )


def _make_storage(*, path: str = "/backups/snap.sql.gz", info: SnapshotInfo | None = None) -> MagicMock:
    """Return a MagicMock conforming to ISnapshotStorage."""
    storage = MagicMock()
    storage.path_of.return_value = path
    storage.info.return_value = info
    storage.rotate.return_value = 0
    return storage


def _make_runner(*, size_bytes: int = 512) -> MagicMock:
    """Return a MagicMock conforming to IBackupRunner."""
    runner = MagicMock()
    runner.dump.return_value = size_bytes
    return runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateSnapshotUseCase:
    def test_calls_dump_with_path_from_storage(self):
        """
        Given storage that resolves a path for the snapshot name,
        When creating a snapshot (no prefix),
        Then runner.dump is called with exactly that resolved path.
        """
        # Arrange
        from system.app.use_cases.create_snapshot_uc import CreateSnapshotUseCase

        expected_path = "/backups/2026-05-18T12-00-00.sql.gz"
        storage = _make_storage(path=expected_path, info=_make_info("2026-05-18T12-00-00.sql.gz"))
        runner = _make_runner()
        uc = CreateSnapshotUseCase(_storage=storage, _runner=runner)

        # Act
        uc()

        # Assert
        runner.dump.assert_called_once_with(expected_path)

    def test_calls_rotate_with_keep_10(self):
        """
        Given a valid storage/runner pair,
        When creating a snapshot,
        Then storage.rotate(keep=10) is called exactly once.
        """
        # Arrange
        from system.app.use_cases.create_snapshot_uc import CreateSnapshotUseCase

        info = _make_info("snap.sql.gz")
        storage = _make_storage(info=info)
        runner = _make_runner()
        uc = CreateSnapshotUseCase(_storage=storage, _runner=runner)

        # Act
        uc()

        # Assert
        storage.rotate.assert_called_once_with(keep=10)

    def test_returns_snapshot_info_from_storage(self):
        """
        Given storage.info returns a SnapshotInfo after dump,
        When creating a snapshot,
        Then the use case returns that SnapshotInfo.
        """
        # Arrange
        from system.app.use_cases.create_snapshot_uc import CreateSnapshotUseCase

        info = _make_info("2026-05-18T12-00-00.sql.gz")
        storage = _make_storage(info=info)
        runner = _make_runner()
        uc = CreateSnapshotUseCase(_storage=storage, _runner=runner)

        # Act
        result = uc()

        # Assert
        assert result is info

    def test_call_order_is_dump_then_rotate_then_info(self):
        """
        Given storage and runner,
        When creating a snapshot,
        Then the order of calls is: path_of → dump → rotate → info.
        """
        # Arrange
        from system.app.use_cases.create_snapshot_uc import CreateSnapshotUseCase

        info = _make_info("snap.sql.gz")
        manager = MagicMock()
        manager.storage.path_of.return_value = "/backups/snap.sql.gz"
        manager.storage.info.return_value = info
        manager.storage.rotate.return_value = 0
        manager.runner.dump.return_value = 512

        uc = CreateSnapshotUseCase(_storage=manager.storage, _runner=manager.runner)

        # Act
        uc()

        # Assert — relative ordering via call list on the manager mock
        calls = manager.mock_calls
        path_of_idx = next(i for i, c in enumerate(calls) if c[0] == "storage.path_of")
        dump_idx    = next(i for i, c in enumerate(calls) if c[0] == "runner.dump")
        rotate_idx  = next(i for i, c in enumerate(calls) if c[0] == "storage.rotate")
        info_idx    = next(i for i, c in enumerate(calls) if c[0] == "storage.info")
        assert path_of_idx < dump_idx < rotate_idx < info_idx

    def test_empty_prefix_produces_non_pre_restore_name(self):
        """
        Given no prefix (default),
        When creating a snapshot,
        Then path_of is called with a name that does NOT start with 'pre-restore-'.
        """
        # Arrange
        from system.app.use_cases.create_snapshot_uc import CreateSnapshotUseCase

        storage = _make_storage(info=_make_info("snap.sql.gz"))
        runner = _make_runner()
        uc = CreateSnapshotUseCase(_storage=storage, _runner=runner)

        # Act
        uc()

        # Assert
        resolved_name: str = storage.path_of.call_args[0][0]
        assert not resolved_name.startswith("pre-restore-")

    def test_pre_restore_prefix_produces_pre_restore_name(self):
        """
        Given prefix='pre-restore-',
        When creating a snapshot,
        Then path_of is called with a name that starts with 'pre-restore-'.
        """
        # Arrange
        from system.app.use_cases.create_snapshot_uc import CreateSnapshotUseCase

        storage = _make_storage(info=_make_info("pre-restore-snap.sql.gz"))
        runner = _make_runner()
        uc = CreateSnapshotUseCase(_storage=storage, _runner=runner)

        # Act
        uc(prefix="pre-restore-")

        # Assert
        resolved_name: str = storage.path_of.call_args[0][0]
        assert resolved_name.startswith("pre-restore-")

    def test_storage_info_is_queried_with_the_generated_name(self):
        """
        Given a generated snapshot name passed to path_of,
        When creating a snapshot,
        Then storage.info is queried with that same name (not a different one).
        """
        # Arrange
        from system.app.use_cases.create_snapshot_uc import CreateSnapshotUseCase

        storage = _make_storage(info=_make_info("snap.sql.gz"))
        runner = _make_runner()
        uc = CreateSnapshotUseCase(_storage=storage, _runner=runner)

        # Act
        uc()

        # Assert
        name_passed_to_path_of = storage.path_of.call_args[0][0]
        name_passed_to_info    = storage.info.call_args[0][0]
        assert name_passed_to_path_of == name_passed_to_info

    def test_storage_info_returning_none_raises_snapshot_missing_after_dump_error(self):
        """
        Given storage.info returns None after a successful dump,
        When creating a snapshot,
        Then SnapshotMissingAfterDumpError is raised.
        """
        # Arrange
        from system.app.use_cases.create_snapshot_uc import CreateSnapshotUseCase
        from system.domain import SnapshotMissingAfterDumpError

        storage = _make_storage(info=None)  # info returns None
        runner = _make_runner()
        uc = CreateSnapshotUseCase(_storage=storage, _runner=runner)

        # Act + Assert
        with pytest.raises(SnapshotMissingAfterDumpError):
            uc()


class TestBuildNamePrefixValidation:
    """Unit-level tests for _build_name prefix guard (Fix 3)."""

    def test_slash_in_prefix_raises_snapshot_name_invalid_error(self):
        """
        Given prefix containing '/',
        When building the name,
        Then SnapshotNameInvalidError is raised.
        """
        from system.app.use_cases.create_snapshot_uc import _build_name
        from system.domain import SnapshotNameInvalidError

        with pytest.raises(SnapshotNameInvalidError):
            _build_name("evil/prefix")

    def test_double_dot_in_prefix_raises_snapshot_name_invalid_error(self):
        """
        Given prefix containing '..',
        When building the name,
        Then SnapshotNameInvalidError is raised.
        """
        from system.app.use_cases.create_snapshot_uc import _build_name
        from system.domain import SnapshotNameInvalidError

        with pytest.raises(SnapshotNameInvalidError):
            _build_name("../../etc/passwd")

    def test_uppercase_in_prefix_raises_snapshot_name_invalid_error(self):
        """
        Given prefix with an uppercase letter (not matching [a-z\\-]*),
        When building the name,
        Then SnapshotNameInvalidError is raised.
        """
        from system.app.use_cases.create_snapshot_uc import _build_name
        from system.domain import SnapshotNameInvalidError

        with pytest.raises(SnapshotNameInvalidError):
            _build_name("Bad-Prefix")

    def test_digit_in_prefix_raises_snapshot_name_invalid_error(self):
        """
        Given prefix with a digit (not matching [a-z\\-]*),
        When building the name,
        Then SnapshotNameInvalidError is raised.
        """
        from system.app.use_cases.create_snapshot_uc import _build_name
        from system.domain import SnapshotNameInvalidError

        with pytest.raises(SnapshotNameInvalidError):
            _build_name("prefix123")

    def test_valid_lowercase_hyphen_prefix_is_accepted(self):
        """
        Given a valid prefix of lowercase letters and hyphens,
        When building the name,
        Then no exception is raised and result contains the prefix.
        """
        from system.app.use_cases.create_snapshot_uc import _build_name

        result = _build_name("pre-restore-")
        assert result.startswith("pre-restore-")

    def test_empty_prefix_is_accepted(self):
        """
        Given an empty prefix (default),
        When building the name,
        Then no exception is raised and result ends with .sql.gz.
        """
        from system.app.use_cases.create_snapshot_uc import _build_name

        result = _build_name("")
        assert result.endswith(".sql.gz")
