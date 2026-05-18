"""
Flow tests for RestoreSnapshotUseCase.

Key invariants under test:
1. Unknown snapshot raises SnapshotNotFoundError BEFORE any pre-restore creation.
2. Happy path: pre-restore → maintenance.enter → restore → apply_migrations
                            → dispose_pool → request_worker_restart → maintenance.exit.
3. Exception during runner.restore still calls maintenance.exit (finally guarantee).
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest

from system.domain import SnapshotInfo, SnapshotNotFoundError

pytestmark = pytest.mark.flow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_info(name: str) -> SnapshotInfo:
    return SnapshotInfo(
        name=name,
        size_bytes=2048,
        created_at=datetime(2026, 5, 18, 10, 0, 0, tzinfo=timezone.utc),
        mig_version=5,
        is_pre_restore=False,
    )


def _make_storage(*, known_name: str | None = "snap.sql.gz") -> MagicMock:
    storage = MagicMock()
    storage.path_of.return_value = f"/backups/{known_name}"
    if known_name is None:
        storage.info.return_value = None
    else:
        storage.info.side_effect = lambda n: _make_info(n) if n == known_name else None
    storage.rotate.return_value = 0
    return storage


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.dump.return_value = 512
    return runner


def _make_maintenance() -> MagicMock:
    return MagicMock()


def _make_create_uc() -> MagicMock:
    """Fake for CreateSnapshotUseCase — callable mock."""
    create_uc = MagicMock()
    create_uc.return_value = _make_info("pre-restore-snap.sql.gz")
    return create_uc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRestoreSnapshotUseCase:
    def test_unknown_name_raises_before_pre_restore(self):
        """
        Given a storage that has no record of the requested snapshot name,
        When restoring,
        Then SnapshotNotFoundError is raised and create_uc is never called.
        """
        # Arrange
        from system.app.use_cases.restore_snapshot_uc import RestoreSnapshotUseCase

        storage = _make_storage(known_name=None)
        storage.info.return_value = None
        runner = _make_runner()
        maintenance = _make_maintenance()
        create_uc = _make_create_uc()
        uc = RestoreSnapshotUseCase(
            _storage=storage,
            _runner=runner,
            _maintenance=maintenance,
            _create_uc=create_uc,
        )

        # Act
        with pytest.raises(SnapshotNotFoundError) as exc_info:
            uc(name="nonexistent.sql.gz")

        # Assert
        assert exc_info.value.name == "nonexistent.sql.gz"
        create_uc.assert_not_called()
        maintenance.enter.assert_not_called()
        runner.restore.assert_not_called()

    def test_happy_path_call_sequence(self):
        """
        Given a storage that knows the requested snapshot name,
        When restoring,
        Then the use case creates a pre-restore snapshot, enters maintenance,
             restores, applies migrations, disposes the pool, requests a restart,
             and finally exits maintenance — in that exact order.
        """
        # Arrange
        from system.app.use_cases.restore_snapshot_uc import RestoreSnapshotUseCase

        manager = MagicMock()
        manager.storage.info.side_effect = lambda n: _make_info(n) if n == "snap.sql.gz" else None
        manager.storage.path_of.return_value = "/backups/snap.sql.gz"
        manager.storage.rotate.return_value = 0
        manager.runner.dump.return_value = 512
        manager.create_uc.return_value = _make_info("pre-restore-snap.sql.gz")

        uc = RestoreSnapshotUseCase(
            _storage=manager.storage,
            _runner=manager.runner,
            _maintenance=manager.maintenance,
            _create_uc=manager.create_uc,
        )

        # Act
        uc(name="snap.sql.gz")

        # Assert — extract call names for ordering verification
        calls = [c[0] for c in manager.mock_calls]
        assert "storage.info" in calls
        assert "create_uc" in calls
        assert "maintenance.enter" in calls
        assert "runner.restore" in calls
        assert "runner.apply_migrations" in calls
        assert "runner.dispose_pool" in calls
        assert "runner.request_worker_restart" in calls
        assert "maintenance.exit" in calls

        idx = {name: calls.index(name) for name in [
            "storage.info",
            "create_uc",
            "maintenance.enter",
            "runner.restore",
            "runner.apply_migrations",
            "runner.dispose_pool",
            "runner.request_worker_restart",
            "maintenance.exit",
        ]}
        assert idx["storage.info"] < idx["create_uc"]
        assert idx["create_uc"] < idx["maintenance.enter"]
        assert idx["maintenance.enter"] < idx["runner.restore"]
        assert idx["runner.restore"] < idx["runner.apply_migrations"]
        assert idx["runner.apply_migrations"] < idx["runner.dispose_pool"]
        assert idx["runner.dispose_pool"] < idx["runner.request_worker_restart"]
        assert idx["runner.request_worker_restart"] < idx["maintenance.exit"]

    def test_pre_restore_create_uc_called_with_pre_restore_prefix(self):
        """
        Given a valid snapshot name,
        When restoring,
        Then create_uc is called with prefix='pre-restore-'.
        """
        # Arrange
        from system.app.use_cases.restore_snapshot_uc import RestoreSnapshotUseCase

        storage = _make_storage(known_name="snap.sql.gz")
        runner = _make_runner()
        maintenance = _make_maintenance()
        create_uc = _make_create_uc()
        uc = RestoreSnapshotUseCase(
            _storage=storage,
            _runner=runner,
            _maintenance=maintenance,
            _create_uc=create_uc,
        )

        # Act
        uc(name="snap.sql.gz")

        # Assert
        create_uc.assert_called_once_with(prefix="pre-restore-")

    def test_runner_restore_called_with_storage_path(self):
        """
        Given a valid snapshot name and storage resolving its path,
        When restoring,
        Then runner.restore is called with the path returned by storage.path_of(name).
        """
        # Arrange
        from system.app.use_cases.restore_snapshot_uc import RestoreSnapshotUseCase

        expected_path = "/backups/snap.sql.gz"
        storage = _make_storage(known_name="snap.sql.gz")
        storage.path_of.return_value = expected_path
        runner = _make_runner()
        maintenance = _make_maintenance()
        create_uc = _make_create_uc()
        uc = RestoreSnapshotUseCase(
            _storage=storage,
            _runner=runner,
            _maintenance=maintenance,
            _create_uc=create_uc,
        )

        # Act
        uc(name="snap.sql.gz")

        # Assert
        runner.restore.assert_called_once_with(expected_path)

    def test_exception_in_restore_still_calls_maintenance_exit(self):
        """
        Given runner.restore raises an exception,
        When restoring,
        Then maintenance.exit is still called (finally block guarantee).
        """
        # Arrange
        from system.app.use_cases.restore_snapshot_uc import RestoreSnapshotUseCase

        storage = _make_storage(known_name="snap.sql.gz")
        runner = _make_runner()
        runner.restore.side_effect = RuntimeError("dump failed")
        maintenance = _make_maintenance()
        create_uc = _make_create_uc()
        uc = RestoreSnapshotUseCase(
            _storage=storage,
            _runner=runner,
            _maintenance=maintenance,
            _create_uc=create_uc,
        )

        # Act
        with pytest.raises(RuntimeError, match="dump failed"):
            uc(name="snap.sql.gz")

        # Assert
        maintenance.exit.assert_called_once()

    def test_exception_in_restore_maintenance_enter_was_called(self):
        """
        Given runner.restore raises,
        When restoring,
        Then maintenance.enter was called before the exception (we did enter).
        """
        # Arrange
        from system.app.use_cases.restore_snapshot_uc import RestoreSnapshotUseCase

        storage = _make_storage(known_name="snap.sql.gz")
        runner = _make_runner()
        runner.restore.side_effect = RuntimeError("disk error")
        maintenance = _make_maintenance()
        create_uc = _make_create_uc()
        uc = RestoreSnapshotUseCase(
            _storage=storage,
            _runner=runner,
            _maintenance=maintenance,
            _create_uc=create_uc,
        )

        # Act
        with pytest.raises(RuntimeError):
            uc(name="snap.sql.gz")

        # Assert
        maintenance.enter.assert_called_once()
        maintenance.exit.assert_called_once()

    def test_exception_propagates_after_maintenance_exit(self):
        """
        Given runner.restore raises,
        When restoring,
        Then the original exception propagates to the caller after maintenance.exit.
        """
        # Arrange
        from system.app.use_cases.restore_snapshot_uc import RestoreSnapshotUseCase

        storage = _make_storage(known_name="snap.sql.gz")
        runner = _make_runner()
        runner.restore.side_effect = ValueError("bad file")
        maintenance = _make_maintenance()
        create_uc = _make_create_uc()
        uc = RestoreSnapshotUseCase(
            _storage=storage,
            _runner=runner,
            _maintenance=maintenance,
            _create_uc=create_uc,
        )

        # Act + Assert
        with pytest.raises(ValueError, match="bad file"):
            uc(name="snap.sql.gz")

    def test_exception_in_maintenance_enter_does_not_call_exit(self):
        """
        Given maintenance.enter raises an exception,
        When restoring,
        Then maintenance.exit is NOT called — enter() happens before the try block,
             so the finally clause that calls exit() is never reached.
        """
        # Arrange
        from system.app.use_cases.restore_snapshot_uc import RestoreSnapshotUseCase

        storage = _make_storage(known_name="snap.sql.gz")
        runner = _make_runner()
        maintenance = _make_maintenance()
        maintenance.enter.side_effect = RuntimeError("cannot enter maintenance")
        create_uc = _make_create_uc()
        uc = RestoreSnapshotUseCase(
            _storage=storage,
            _runner=runner,
            _maintenance=maintenance,
            _create_uc=create_uc,
        )

        # Act
        with pytest.raises(RuntimeError, match="cannot enter maintenance"):
            uc(name="snap.sql.gz")

        # Assert — exit must NOT have been called because the try block was
        # never entered (maintenance.enter() is outside the try/finally).
        maintenance.exit.assert_not_called()
