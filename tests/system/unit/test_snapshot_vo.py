import dataclasses
from datetime import datetime

import pytest

from system.domain.snapshot_vo import SnapshotInfo


@pytest.mark.unit
class TestSnapshotInfoDisplayName:
    def test_removes_sql_gz_suffix(self) -> None:
        info = SnapshotInfo(
            name="2026-05-18-mig0001.sql.gz",
            size_bytes=1024,
            created_at=datetime(2026, 5, 18),
            mig_version=1,
            is_pre_restore=False,
        )
        assert info.display_name == "2026-05-18-mig0001"

    def test_name_without_suffix_unchanged(self) -> None:
        info = SnapshotInfo(
            name="2026-05-18-mig0001",
            size_bytes=1024,
            created_at=datetime(2026, 5, 18),
            mig_version=1,
            is_pre_restore=False,
        )
        assert info.display_name == "2026-05-18-mig0001"


@pytest.mark.unit
class TestSnapshotInfoIsPreRestore:
    def test_pre_restore_snapshot_is_flagged(self) -> None:
        info = SnapshotInfo(
            name="pre-restore-2026-05-18.sql.gz",
            size_bytes=512,
            created_at=datetime(2026, 5, 18),
            mig_version=0,
            is_pre_restore=True,
        )
        assert info.is_pre_restore is True

    def test_regular_snapshot_is_not_pre_restore(self) -> None:
        info = SnapshotInfo(
            name="2026-05-18.sql.gz",
            size_bytes=512,
            created_at=datetime(2026, 5, 18),
            mig_version=0,
            is_pre_restore=False,
        )
        assert info.is_pre_restore is False


@pytest.mark.unit
class TestSnapshotInfoFrozen:
    def test_assigning_name_raises_frozen_instance_error(self) -> None:
        info = SnapshotInfo(
            name="2026-05-18.sql.gz",
            size_bytes=256,
            created_at=datetime(2026, 5, 18),
            mig_version=0,
            is_pre_restore=False,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.name = "other.sql.gz"  # type: ignore[misc]


@pytest.mark.unit
class TestSnapshotInfoEquality:
    def test_two_identical_instances_are_equal(self) -> None:
        dt = datetime(2026, 5, 18, 12, 0, 0)
        a = SnapshotInfo(
            name="snap.sql.gz",
            size_bytes=2048,
            created_at=dt,
            mig_version=3,
            is_pre_restore=False,
        )
        b = SnapshotInfo(
            name="snap.sql.gz",
            size_bytes=2048,
            created_at=dt,
            mig_version=3,
            is_pre_restore=False,
        )
        assert a == b

    def test_different_name_means_not_equal(self) -> None:
        dt = datetime(2026, 5, 18)
        a = SnapshotInfo(
            name="snap-a.sql.gz",
            size_bytes=100,
            created_at=dt,
            mig_version=0,
            is_pre_restore=False,
        )
        b = SnapshotInfo(
            name="snap-b.sql.gz",
            size_bytes=100,
            created_at=dt,
            mig_version=0,
            is_pre_restore=False,
        )
        assert a != b
