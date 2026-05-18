"""
Flow tests for ListSnapshotsQuery.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from system.domain import SnapshotInfo

pytestmark = pytest.mark.flow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _info(name: str, *, year: int, month: int, day: int, hour: int = 0) -> SnapshotInfo:
    return SnapshotInfo(
        name=name,
        size_bytes=256,
        created_at=datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc),
        mig_version=1,
        is_pre_restore=False,
    )


def _make_storage(items: list[SnapshotInfo]) -> MagicMock:
    storage = MagicMock()
    storage.list.return_value = list(items)
    return storage


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestListSnapshotsQuery:
    def test_returns_snapshots_sorted_newest_first(self):
        """
        Given a storage with three snapshots at different timestamps,
        When listing,
        Then the query returns them sorted by created_at descending.
        """
        # Arrange
        from system.app.queries.list_snapshots_query import ListSnapshotsQuery

        oldest  = _info("old.sql.gz",    year=2026, month=1, day=1)
        middle  = _info("mid.sql.gz",    year=2026, month=3, day=15)
        newest  = _info("new.sql.gz",    year=2026, month=5, day=18)
        storage = _make_storage([middle, oldest, newest])  # deliberately unordered
        query = ListSnapshotsQuery(_storage=storage)

        # Act
        result = query()

        # Assert
        assert result == [newest, middle, oldest]

    def test_empty_storage_returns_empty_list(self):
        """
        Given a storage with no snapshots,
        When listing,
        Then the query returns an empty list.
        """
        # Arrange
        from system.app.queries.list_snapshots_query import ListSnapshotsQuery

        storage = _make_storage([])
        query = ListSnapshotsQuery(_storage=storage)

        # Act
        result = query()

        # Assert
        assert result == []

    def test_single_snapshot_returned_as_single_element_list(self):
        """
        Given a storage with exactly one snapshot,
        When listing,
        Then the query returns a list with that one element.
        """
        # Arrange
        from system.app.queries.list_snapshots_query import ListSnapshotsQuery

        snap = _info("only.sql.gz", year=2026, month=5, day=1)
        storage = _make_storage([snap])
        query = ListSnapshotsQuery(_storage=storage)

        # Act
        result = query()

        # Assert
        assert result == [snap]

    def test_does_not_mutate_storage_list(self):
        """
        Given a storage list in a particular order,
        When listing,
        Then the original list returned by storage.list is not mutated.
        """
        # Arrange
        from system.app.queries.list_snapshots_query import ListSnapshotsQuery

        snaps = [
            _info("b.sql.gz", year=2026, month=2, day=1),
            _info("a.sql.gz", year=2026, month=1, day=1),
        ]
        original_order = list(snaps)
        storage = _make_storage(snaps)
        query = ListSnapshotsQuery(_storage=storage)

        # Act
        query()

        # Assert — storage.list return value was not mutated in place
        assert storage.list.return_value == original_order

    def test_calls_storage_list_exactly_once(self):
        """
        Given a storage,
        When listing,
        Then storage.list is called exactly once per query invocation.
        """
        # Arrange
        from system.app.queries.list_snapshots_query import ListSnapshotsQuery

        storage = _make_storage([])
        query = ListSnapshotsQuery(_storage=storage)

        # Act
        query()

        # Assert
        storage.list.assert_called_once_with()
