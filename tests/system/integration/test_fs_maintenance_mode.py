"""
Integration tests for FsMaintenanceMode.

All tests use tmp_path (real filesystem via pytest fixture).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


def _make_maintenance(flag_path: Path):
    from system.ports.driven.fs_maintenance_mode import FsMaintenanceMode
    return FsMaintenanceMode(_flag_path=flag_path)


class TestFsMaintenanceModeEnter:
    def test_enter_creates_flag_file(self, tmp_path):
        """
        Given a flag path that does not exist,
        When enter() is called,
        Then the flag file is created.
        """
        # Arrange
        flag = tmp_path / "data" / ".maintenance"
        mm = _make_maintenance(flag)

        # Act
        mm.enter()

        # Assert
        assert flag.exists()

    def test_enter_creates_parent_directories(self, tmp_path):
        """
        Given a flag path with non-existent parent directories,
        When enter() is called,
        Then all parent directories are created and the flag file exists.
        """
        # Arrange
        flag = tmp_path / "deeply" / "nested" / "dir" / ".maintenance"
        mm = _make_maintenance(flag)

        # Act
        mm.enter()

        # Assert
        assert flag.exists()

    def test_enter_is_idempotent(self, tmp_path):
        """
        Given a flag file already exists,
        When enter() is called again,
        Then no exception is raised and file still exists.
        """
        # Arrange
        flag = tmp_path / ".maintenance"
        mm = _make_maintenance(flag)
        mm.enter()

        # Act + Assert (no exception)
        mm.enter()
        assert flag.exists()

    def test_enter_wraps_oserror_as_driven_port_error(self, tmp_path):
        """
        Given a PermissionError raised when creating the parent directory,
        When enter() is called,
        Then DrivenPortError is raised with code MAINTENANCE_FAILED.
        """
        # Arrange
        from shared.generics.errors import DrivenPortError
        flag = tmp_path / "data" / ".maintenance"
        mm = _make_maintenance(flag)

        with patch.object(Path, "mkdir", side_effect=PermissionError("permission denied")):
            # Act + Assert
            with pytest.raises(DrivenPortError) as exc_info:
                mm.enter()

        assert exc_info.value.code == "MAINTENANCE_FAILED"
        assert "enter" in str(exc_info.value).lower() or "maintenance" in str(exc_info.value).lower()


class TestFsMaintenanceModeExit:
    def test_exit_removes_flag_file(self, tmp_path):
        """
        Given the maintenance flag file exists,
        When exit() is called,
        Then the flag file is removed.
        """
        # Arrange
        flag = tmp_path / ".maintenance"
        flag.touch()
        mm = _make_maintenance(flag)

        # Act
        mm.exit()

        # Assert
        assert not flag.exists()

    def test_exit_on_missing_file_does_not_raise(self, tmp_path):
        """
        Given the flag file does not exist,
        When exit() is called,
        Then no exception is raised.
        """
        # Arrange
        flag = tmp_path / ".maintenance"
        mm = _make_maintenance(flag)

        # Act + Assert (no exception)
        mm.exit()

    def test_exit_twice_does_not_raise(self, tmp_path):
        """
        Given exit() has already been called once,
        When exit() is called again,
        Then no exception is raised.
        """
        # Arrange
        flag = tmp_path / ".maintenance"
        flag.touch()
        mm = _make_maintenance(flag)
        mm.exit()

        # Act + Assert (no exception)
        mm.exit()

    def test_exit_wraps_oserror_as_driven_port_error(self, tmp_path):
        """
        Given a PermissionError raised when unlinking the flag file,
        When exit() is called,
        Then DrivenPortError is raised with code MAINTENANCE_FAILED.
        """
        # Arrange
        from shared.generics.errors import DrivenPortError
        flag = tmp_path / ".maintenance"
        flag.touch()
        mm = _make_maintenance(flag)

        with patch.object(Path, "unlink", side_effect=PermissionError("permission denied")):
            # Act + Assert
            with pytest.raises(DrivenPortError) as exc_info:
                mm.exit()

        assert exc_info.value.code == "MAINTENANCE_FAILED"
        assert "exit" in str(exc_info.value).lower() or "maintenance" in str(exc_info.value).lower()
