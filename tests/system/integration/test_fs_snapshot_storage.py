"""
Integration tests for FsSnapshotStorage.

All tests use tmp_path (real filesystem via pytest fixture).
No external services required.
"""
from __future__ import annotations

import os
import time
from datetime import timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sql_gz(directory: Path, name: str, content: bytes = b"x") -> Path:
    """Create a .sql.gz file with minimal content."""
    p = directory / name
    p.write_bytes(content)
    return p


def _make_storage(dumps_dir: Path):
    from system.ports.driven.fs_snapshot_storage import FsSnapshotStorage
    return FsSnapshotStorage(_dumps_dir=dumps_dir)


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------

class TestFsSnapshotStorageList:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        """
        Given an empty dumps directory,
        When listing snapshots,
        Then an empty list is returned.
        """
        # Arrange
        storage = _make_storage(tmp_path)

        # Act
        result = storage.list()

        # Assert
        assert result == []

    def test_three_sql_gz_files_returns_three_entries(self, tmp_path):
        """
        Given three .sql.gz files in the dumps directory,
        When listing snapshots,
        Then three SnapshotInfo entries are returned with correct names.
        """
        # Arrange
        names = [
            "1-20260518T120000Z.sql.gz",
            "2-20260518T130000Z.sql.gz",
            "3-20260518T140000Z.sql.gz",
        ]
        for name in names:
            _make_sql_gz(tmp_path, name)
        storage = _make_storage(tmp_path)

        # Act
        result = storage.list()

        # Assert
        assert len(result) == 3
        result_names = {s.name for s in result}
        assert result_names == set(names)

    def test_non_sql_gz_files_are_ignored(self, tmp_path):
        """
        Given a mix of .sql.gz and other files,
        When listing snapshots,
        Then only .sql.gz files are returned.
        """
        # Arrange
        _make_sql_gz(tmp_path, "1-20260518T120000Z.sql.gz")
        (tmp_path / "readme.txt").write_text("ignore me")
        (tmp_path / "backup.sql").write_bytes(b"ignore me too")
        storage = _make_storage(tmp_path)

        # Act
        result = storage.list()

        # Assert
        assert len(result) == 1
        assert result[0].name == "1-20260518T120000Z.sql.gz"


# ---------------------------------------------------------------------------
# rotate()
# ---------------------------------------------------------------------------

class TestFsSnapshotStorageRotate:
    def test_rotate_keeps_two_newest_deletes_three_oldest(self, tmp_path):
        """
        Given 5 non-pre-restore .sql.gz files with distinct mtimes,
        When rotate(keep=2) is called,
        Then 3 oldest files are deleted and 2 newest remain.
        """
        # Arrange
        names = [
            "1-20260518T100000Z.sql.gz",
            "2-20260518T110000Z.sql.gz",
            "3-20260518T120000Z.sql.gz",
            "4-20260518T130000Z.sql.gz",
            "5-20260518T140000Z.sql.gz",
        ]
        for i, name in enumerate(names):
            p = _make_sql_gz(tmp_path, name)
            # Touch with staggered mtimes so ordering is deterministic
            t = 1_700_000_000 + i * 60
            os.utime(p, (t, t))

        storage = _make_storage(tmp_path)

        # Act
        deleted_count = storage.rotate(keep=2)

        # Assert
        assert deleted_count == 3
        remaining = list(tmp_path.glob("*.sql.gz"))
        assert len(remaining) == 2
        remaining_names = {p.name for p in remaining}
        # The two newest by mtime should survive
        assert "5-20260518T140000Z.sql.gz" in remaining_names
        assert "4-20260518T130000Z.sql.gz" in remaining_names

    def test_rotate_does_not_touch_pre_restore_files(self, tmp_path):
        """
        Given 5 pre-restore .sql.gz files and keep=0,
        When rotate() is called,
        Then no pre-restore files are deleted.
        """
        # Arrange
        names = [
            "pre-restore-1-20260518T100000Z.sql.gz",
            "pre-restore-2-20260518T110000Z.sql.gz",
            "pre-restore-3-20260518T120000Z.sql.gz",
            "pre-restore-4-20260518T130000Z.sql.gz",
            "pre-restore-5-20260518T140000Z.sql.gz",
        ]
        for name in names:
            _make_sql_gz(tmp_path, name)

        storage = _make_storage(tmp_path)

        # Act
        deleted_count = storage.rotate(keep=0)

        # Assert
        assert deleted_count == 0
        assert len(list(tmp_path.glob("*.sql.gz"))) == 5

    def test_rotate_with_mix_only_removes_non_pre_restore(self, tmp_path):
        """
        Given 3 regular + 2 pre-restore files with keep=1,
        When rotate() is called,
        Then 2 regular files are removed, pre-restore files intact.
        """
        # Arrange
        regular_names = [
            "1-20260518T100000Z.sql.gz",
            "2-20260518T110000Z.sql.gz",
            "3-20260518T120000Z.sql.gz",
        ]
        pre_restore_names = [
            "pre-restore-1-20260518T100000Z.sql.gz",
            "pre-restore-2-20260518T110000Z.sql.gz",
        ]
        for i, name in enumerate(regular_names):
            p = _make_sql_gz(tmp_path, name)
            t = 1_700_000_000 + i * 60
            os.utime(p, (t, t))
        for name in pre_restore_names:
            _make_sql_gz(tmp_path, name)

        storage = _make_storage(tmp_path)

        # Act
        deleted_count = storage.rotate(keep=1)

        # Assert
        assert deleted_count == 2
        remaining = list(tmp_path.glob("*.sql.gz"))
        assert len(remaining) == 3  # 1 regular + 2 pre-restore
        remaining_names = {p.name for p in remaining}
        assert "pre-restore-1-20260518T100000Z.sql.gz" in remaining_names
        assert "pre-restore-2-20260518T110000Z.sql.gz" in remaining_names

    def test_rotate_returns_zero_when_fewer_files_than_keep(self, tmp_path):
        """
        Given 2 files and keep=5,
        When rotate() is called,
        Then 0 files are deleted.
        """
        # Arrange
        _make_sql_gz(tmp_path, "1-20260518T120000Z.sql.gz")
        _make_sql_gz(tmp_path, "2-20260518T130000Z.sql.gz")
        storage = _make_storage(tmp_path)

        # Act
        deleted_count = storage.rotate(keep=5)

        # Assert
        assert deleted_count == 0
        assert len(list(tmp_path.glob("*.sql.gz"))) == 2


# ---------------------------------------------------------------------------
# path_of() — security / validation
# ---------------------------------------------------------------------------

class TestFsSnapshotStoragePathOf:
    def test_path_traversal_with_parent_segments_raises(self, tmp_path):
        """
        Given a name containing '../',
        When path_of() is called,
        Then SnapshotNameInvalidError is raised.
        """
        # Arrange
        from system.domain import SnapshotNameInvalidError
        storage = _make_storage(tmp_path)

        # Act + Assert
        with pytest.raises(SnapshotNameInvalidError):
            storage.path_of("../etc/passwd.sql.gz")

    def test_name_without_sql_gz_suffix_raises(self, tmp_path):
        """
        Given a name that does not end with .sql.gz,
        When path_of() is called,
        Then SnapshotNameInvalidError is raised.
        """
        # Arrange
        from system.domain import SnapshotNameInvalidError
        storage = _make_storage(tmp_path)

        # Act + Assert
        with pytest.raises(SnapshotNameInvalidError):
            storage.path_of("../sneaky")

    def test_name_with_forward_slash_raises(self, tmp_path):
        """
        Given a name containing a forward slash,
        When path_of() is called,
        Then SnapshotNameInvalidError is raised.
        """
        # Arrange
        from system.domain import SnapshotNameInvalidError
        storage = _make_storage(tmp_path)

        # Act + Assert
        with pytest.raises(SnapshotNameInvalidError):
            storage.path_of("subdir/evil.sql.gz")

    def test_valid_name_returns_absolute_path(self, tmp_path):
        """
        Given a valid snapshot name,
        When path_of() is called,
        Then an absolute path string under dumps_dir is returned.
        """
        # Arrange
        storage = _make_storage(tmp_path)

        # Act
        result = storage.path_of("5-20260518T140000Z.sql.gz")

        # Assert
        assert result == str(tmp_path / "5-20260518T140000Z.sql.gz")


# ---------------------------------------------------------------------------
# info()
# ---------------------------------------------------------------------------

class TestFsSnapshotStorageInfo:
    def test_info_on_missing_name_returns_none(self, tmp_path):
        """
        Given a name that does not exist in the directory,
        When info() is called,
        Then None is returned.
        """
        # Arrange
        storage = _make_storage(tmp_path)

        # Act
        result = storage.info("missing.sql.gz")

        # Assert
        assert result is None

    def test_info_on_existing_file_returns_snapshot_info(self, tmp_path):
        """
        Given a valid .sql.gz file in the directory,
        When info() is called with its name,
        Then a SnapshotInfo with correct name is returned.
        """
        # Arrange
        name = "3-20260518T120000Z.sql.gz"
        _make_sql_gz(tmp_path, name, content=b"data" * 100)
        storage = _make_storage(tmp_path)

        # Act
        result = storage.info(name)

        # Assert
        assert result is not None
        assert result.name == name
        assert result.size_bytes > 0

    def test_info_with_path_traversal_name_returns_none(self, tmp_path):
        """
        Given a name containing path-traversal sequences,
        When info() is called,
        Then None is returned (invalid names treated as not found).
        """
        # Arrange
        storage = _make_storage(tmp_path)

        # Act
        result = storage.info("../etc/passwd.sql.gz")

        # Assert
        assert result is None

    def test_info_with_slash_in_name_returns_none(self, tmp_path):
        """
        Given a name containing a forward slash,
        When info() is called,
        Then None is returned.
        """
        # Arrange
        storage = _make_storage(tmp_path)

        # Act
        result = storage.info("subdir/evil.sql.gz")

        # Assert
        assert result is None


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------

class TestFsSnapshotStorageDelete:
    def test_delete_missing_file_raises_snapshot_not_found(self, tmp_path):
        """
        Given a name that does not exist,
        When delete() is called,
        Then SnapshotNotFoundError is raised.
        """
        # Arrange
        from system.domain import SnapshotNotFoundError
        storage = _make_storage(tmp_path)

        # Act + Assert
        with pytest.raises(SnapshotNotFoundError):
            storage.delete("missing.sql.gz")

    def test_delete_existing_file_removes_it(self, tmp_path):
        """
        Given an existing .sql.gz file,
        When delete() is called,
        Then the file no longer exists.
        """
        # Arrange
        name = "1-20260518T120000Z.sql.gz"
        _make_sql_gz(tmp_path, name)
        storage = _make_storage(tmp_path)

        # Act
        storage.delete(name)

        # Assert
        assert not (tmp_path / name).exists()

    def test_delete_with_path_traversal_raises_snapshot_name_invalid(self, tmp_path):
        """
        Given a name containing path-traversal sequences,
        When delete() is called,
        Then SnapshotNameInvalidError is raised (not SnapshotNotFoundError).
        """
        # Arrange
        from system.domain import SnapshotNameInvalidError
        storage = _make_storage(tmp_path)

        # Act + Assert
        with pytest.raises(SnapshotNameInvalidError):
            storage.delete("../etc/passwd.sql.gz")

    def test_delete_with_slash_in_name_raises_snapshot_name_invalid(self, tmp_path):
        """
        Given a name containing a forward slash,
        When delete() is called,
        Then SnapshotNameInvalidError is raised.
        """
        # Arrange
        from system.domain import SnapshotNameInvalidError
        storage = _make_storage(tmp_path)

        # Act + Assert
        with pytest.raises(SnapshotNameInvalidError):
            storage.delete("subdir/evil.sql.gz")


# ---------------------------------------------------------------------------
# _info() — mig_version parsing
# ---------------------------------------------------------------------------

class TestFsSnapshotStorageInfoParsing:
    def _info(self, tmp_path: Path, name: str):
        p = _make_sql_gz(tmp_path, name)
        from system.ports.driven.fs_snapshot_storage import FsSnapshotStorage
        storage = FsSnapshotStorage(_dumps_dir=tmp_path)
        return storage._info(p)

    def test_parses_mig_version_from_regular_name(self, tmp_path):
        """
        Given filename '5-20260518T120000Z.sql.gz',
        When _info() is called,
        Then mig_version == 5 and is_pre_restore == False.
        """
        result = self._info(tmp_path, "5-20260518T120000Z.sql.gz")
        assert result.mig_version == 5
        assert result.is_pre_restore is False

    def test_parses_mig_version_from_pre_restore_name(self, tmp_path):
        """
        Given filename 'pre-restore-7-20260518T120000Z.sql.gz',
        When _info() is called,
        Then mig_version == 7 and is_pre_restore == True.
        """
        result = self._info(tmp_path, "pre-restore-7-20260518T120000Z.sql.gz")
        assert result.mig_version == 7
        assert result.is_pre_restore is True

    def test_unparseable_mig_version_defaults_to_zero(self, tmp_path):
        """
        Given filename 'backup-no-version.sql.gz',
        When _info() is called,
        Then mig_version == 0.
        """
        result = self._info(tmp_path, "backup-no-version.sql.gz")
        assert result.mig_version == 0

    def test_created_at_has_utc_timezone(self, tmp_path):
        """
        Given any .sql.gz file,
        When _info() is called,
        Then created_at has UTC timezone.
        """
        result = self._info(tmp_path, "1-20260518T120000Z.sql.gz")
        assert result.created_at.tzinfo is not None
        assert result.created_at.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# available_bytes()
# ---------------------------------------------------------------------------

class TestFsSnapshotStorageAvailableBytes:
    def test_available_bytes_returns_positive_int(self, tmp_path):
        """
        Given a real filesystem path,
        When available_bytes() is called,
        Then a positive integer is returned.
        """
        # Arrange
        storage = _make_storage(tmp_path)

        # Act
        result = storage.available_bytes()

        # Assert
        assert isinstance(result, int)
        assert result > 0
