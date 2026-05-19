"""
Flow tests for SystemFacade backup methods.

Given SystemFacade with mocked backup use cases / queries,
verify delegation, return types, and call arguments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from system.domain.snapshot_vo import SnapshotInfo
from system.ports.driving.facade import SystemFacade
from system.ports.driving.schemas import SnapshotListOut, SnapshotOut

pytestmark = pytest.mark.flow


def _snapshot_info(name: str = "2026-01-01T00-00-00.sql.gz") -> SnapshotInfo:
    return SnapshotInfo(
        name=name,
        size_bytes=1024,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        mig_version=2,
        is_pre_restore=False,
    )


def _build_facade(
    *,
    list_snapshots_query=None,
    create_snapshot_uc=None,
    restore_snapshot_uc=None,
    delete_snapshot_uc=None,
) -> SystemFacade:
    """Build a SystemFacade with mocks for everything except backup deps."""
    return SystemFacade(
        _config=MagicMock(),
        _root_config=MagicMock(),
        _get_query=MagicMock(),
        _get_storage_query=MagicMock(),
        _manage_uc=MagicMock(),
        _manage_storage_uc=MagicMock(),
        _test_notify_uc=MagicMock(),
        _recover_password_uc=MagicMock(),
        _fetch_chat_id_uc=MagicMock(),
        _notification_channel=MagicMock(),
        _telegram_client=MagicMock(),
        _list_snapshots_query=list_snapshots_query or MagicMock(),
        _create_snapshot_uc=create_snapshot_uc or MagicMock(),
        _restore_snapshot_uc=restore_snapshot_uc or MagicMock(),
        _delete_snapshot_uc=delete_snapshot_uc or MagicMock(),
    )


class TestListSnapshots:
    def test_delegates_to_query_and_wraps_result(self):
        """
        Given a query that returns one SnapshotInfo,
        When list_snapshots() is called,
        Then returns SnapshotListOut with one SnapshotOut item.
        """
        # Arrange
        info = _snapshot_info()
        query = MagicMock(return_value=[info])
        facade = _build_facade(list_snapshots_query=query)

        # Act
        result = facade.list_snapshots()

        # Assert
        query.assert_called_once_with()
        assert isinstance(result, SnapshotListOut)
        assert len(result.items) == 1
        assert result.items[0].name == info.name
        assert result.items[0].size_bytes == info.size_bytes
        assert result.items[0].is_pre_restore is False
        assert result.items[0].display_name == info.display_name

    def test_empty_list_returns_empty_snapshot_list_out(self):
        """
        Given a query that returns an empty list,
        When list_snapshots() is called,
        Then returns SnapshotListOut with no items.
        """
        # Arrange
        query = MagicMock(return_value=[])
        facade = _build_facade(list_snapshots_query=query)

        # Act
        result = facade.list_snapshots()

        # Assert
        assert isinstance(result, SnapshotListOut)
        assert result.items == []


class TestCreateSnapshot:
    def test_delegates_to_uc_with_empty_prefix_and_wraps_result(self):
        """
        Given a create use case that returns a SnapshotInfo,
        When create_snapshot() is called,
        Then use case is called with prefix="" and SnapshotOut is returned.
        """
        # Arrange
        info = _snapshot_info()
        uc = MagicMock(return_value=info)
        facade = _build_facade(create_snapshot_uc=uc)

        # Act
        result = facade.create_snapshot()

        # Assert
        uc.assert_called_once_with(prefix="")
        assert isinstance(result, SnapshotOut)
        assert result.name == info.name
        assert result.mig_version == info.mig_version
        assert result.created_at == info.created_at


class TestRestoreSnapshot:
    def test_delegates_to_uc_with_name(self):
        """
        Given a restore use case,
        When restore_snapshot(name="foo.sql.gz") is called,
        Then use case is called with name="foo.sql.gz" and returns None.
        """
        # Arrange
        uc = MagicMock(return_value=None)
        facade = _build_facade(restore_snapshot_uc=uc)

        # Act
        result = facade.restore_snapshot(name="foo.sql.gz")

        # Assert
        uc.assert_called_once_with(name="foo.sql.gz")
        assert result is None

    def test_propagates_exception_from_uc(self):
        """
        Given a restore use case that raises SnapshotNotFoundError,
        When restore_snapshot is called,
        Then the exception propagates to the caller.
        """
        # Arrange
        from system.domain.backup_errors import SnapshotNotFoundError

        uc = MagicMock(side_effect=SnapshotNotFoundError("ghost.sql.gz"))
        facade = _build_facade(restore_snapshot_uc=uc)

        # Act & Assert
        with pytest.raises(SnapshotNotFoundError):
            facade.restore_snapshot(name="ghost.sql.gz")


class TestDeleteSnapshot:
    def test_delegates_to_uc_with_name(self):
        """
        Given a delete use case,
        When delete_snapshot(name="foo.sql.gz") is called,
        Then use case is called with name="foo.sql.gz" and returns None.
        """
        # Arrange
        uc = MagicMock(return_value=None)
        facade = _build_facade(delete_snapshot_uc=uc)

        # Act
        result = facade.delete_snapshot(name="foo.sql.gz")

        # Assert
        uc.assert_called_once_with(name="foo.sql.gz")
        assert result is None

    def test_propagates_exception_from_uc(self):
        """
        Given a delete use case that raises SnapshotNotFoundError,
        When delete_snapshot is called,
        Then the exception propagates to the caller.
        """
        # Arrange
        from system.domain.backup_errors import SnapshotNotFoundError

        uc = MagicMock(side_effect=SnapshotNotFoundError("missing.sql.gz"))
        facade = _build_facade(delete_snapshot_uc=uc)

        # Act & Assert
        with pytest.raises(SnapshotNotFoundError):
            facade.delete_snapshot(name="missing.sql.gz")
