"""
Flow tests for DeleteSnapshotUseCase.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from system.domain import SnapshotInfo, SnapshotNotFoundError

pytestmark = pytest.mark.flow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_info(name: str) -> SnapshotInfo:
    return SnapshotInfo(
        name=name,
        size_bytes=512,
        created_at=datetime(2026, 5, 18, 9, 0, 0, tzinfo=timezone.utc),
        mig_version=3,
        is_pre_restore=False,
    )


def _make_storage(*, known_name: str | None = "snap.sql.gz") -> MagicMock:
    storage = MagicMock()
    if known_name is None:
        storage.info.return_value = None
    else:
        storage.info.side_effect = lambda n: _make_info(n) if n == known_name else None
    return storage


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeleteSnapshotUseCase:
    def test_deletes_existing_snapshot(self):
        """
        Given a storage that knows the requested snapshot name,
        When deleting,
        Then storage.delete is called with that name.
        """
        # Arrange
        from system.app.use_cases.delete_snapshot_uc import DeleteSnapshotUseCase

        storage = _make_storage(known_name="snap.sql.gz")
        uc = DeleteSnapshotUseCase(_storage=storage)

        # Act
        uc(name="snap.sql.gz")

        # Assert
        storage.delete.assert_called_once_with("snap.sql.gz")

    def test_missing_snapshot_raises_not_found_without_deleting(self):
        """
        Given a storage that has no record of the requested snapshot name,
        When deleting,
        Then SnapshotNotFoundError is raised and storage.delete is never called.
        """
        # Arrange
        from system.app.use_cases.delete_snapshot_uc import DeleteSnapshotUseCase

        storage = _make_storage(known_name=None)
        storage.info.return_value = None
        uc = DeleteSnapshotUseCase(_storage=storage)

        # Act
        with pytest.raises(SnapshotNotFoundError) as exc_info:
            uc(name="ghost.sql.gz")

        # Assert
        assert exc_info.value.name == "ghost.sql.gz"
        storage.delete.assert_not_called()

    def test_info_checked_before_delete(self):
        """
        Given a known snapshot name,
        When deleting,
        Then storage.info is called before storage.delete (guard-then-act).
        """
        # Arrange
        from system.app.use_cases.delete_snapshot_uc import DeleteSnapshotUseCase

        manager = MagicMock()
        manager.storage.info.return_value = _make_info("snap.sql.gz")
        uc = DeleteSnapshotUseCase(_storage=manager.storage)

        # Act
        uc(name="snap.sql.gz")

        # Assert
        calls = [c[0] for c in manager.mock_calls]
        assert calls.index("storage.info") < calls.index("storage.delete")
