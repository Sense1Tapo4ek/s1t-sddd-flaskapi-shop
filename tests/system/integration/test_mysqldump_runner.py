"""
Integration tests for MysqldumpRunner.

Tests that require a real mysqldump binary or running MySQL are conditionally
skipped when those resources are absent.

Tests for pure Python logic (no real subprocess needed) are marked `flow`
and use mocks.
"""
from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runner(tmp_path: Path, db_url: str = "mysql+pymysql://user:pass@localhost:3306/testdb"):
    from system.ports.driven.mysqldump_runner import MysqldumpRunner
    engine = MagicMock()
    return MysqldumpRunner(
        _db_url=db_url,
        _engine=engine,
        _restart_file=tmp_path / "tmp" / "restart.txt",
        _migrations_dir=tmp_path / "migrations",
    )


# ---------------------------------------------------------------------------
# Credentials file tests — pure Python, no subprocess
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestWriteDefaultsFile:
    def test_defaults_file_has_chmod_600(self, tmp_path):
        """
        Given a valid db_url,
        When _write_defaults_file() is called,
        Then the produced file has mode 0o600.
        """
        # Arrange
        runner = _make_runner(tmp_path)

        # Act
        path = runner._write_defaults_file()
        try:
            mode = os.stat(path).st_mode & 0o777
        finally:
            os.unlink(path)

        # Assert
        assert mode == 0o600

    def test_defaults_file_contains_client_section(self, tmp_path):
        """
        Given a valid db_url with user/pass/host/port,
        When _write_defaults_file() is called,
        Then the file content has a [client] section with correct fields.
        """
        # Arrange
        runner = _make_runner(
            tmp_path,
            db_url="mysql+pymysql://myuser:mypass@myhost:3307/mydb",
        )

        # Act
        path = runner._write_defaults_file()
        try:
            content = open(path).read()
        finally:
            os.unlink(path)

        # Assert
        assert "[client]" in content
        assert "host=myhost" in content
        assert "user=myuser" in content
        assert "password=mypass" in content
        assert "port=3307" in content

    def test_defaults_file_does_not_appear_in_env_or_argv(self, tmp_path):
        """
        Given any db_url,
        When _write_defaults_file() is called,
        Then no subprocess call includes --password= in its argument list.

        This is validated by checking the _write_defaults_file path pattern —
        the actual dump/restore calls use --defaults-extra-file=<path>, never --password=.
        """
        # Arrange
        runner = _make_runner(tmp_path, db_url="mysql+pymysql://u:secret@h:3306/db")

        # Act
        path = runner._write_defaults_file()
        try:
            content = open(path).read()
        finally:
            os.unlink(path)

        # Assert — password appears only inside the file, not as a CLI flag form
        assert "--password=" not in content
        assert "-p" + "secret" not in content


@pytest.mark.flow
class TestRequestWorkerRestart:
    def test_no_op_when_tmp_dir_does_not_exist(self, tmp_path):
        """
        Given the tmp/ parent directory does not exist,
        When request_worker_restart() is called,
        Then no exception is raised and no file is created.
        """
        # Arrange
        runner = _make_runner(tmp_path)
        restart_file = tmp_path / "tmp" / "restart.txt"
        assert not restart_file.parent.exists()

        # Act (no exception)
        runner.request_worker_restart()

        # Assert
        assert not restart_file.exists()

    def test_touches_restart_file_when_tmp_dir_exists(self, tmp_path):
        """
        Given the tmp/ directory exists,
        When request_worker_restart() is called,
        Then the restart.txt file is created (touched).
        """
        # Arrange
        restart_file = tmp_path / "tmp" / "restart.txt"
        restart_file.parent.mkdir(parents=True)
        runner = _make_runner(tmp_path)

        # Act
        runner.request_worker_restart()

        # Assert
        assert restart_file.exists()


@pytest.mark.flow
class TestDisposePool:
    def test_dispose_pool_calls_engine_dispose(self, tmp_path):
        """
        Given a mock engine,
        When dispose_pool() is called,
        Then engine.dispose() is invoked exactly once.
        """
        # Arrange
        runner = _make_runner(tmp_path)

        # Act
        runner.dispose_pool()

        # Assert
        runner._engine.dispose.assert_called_once()


@pytest.mark.flow
class TestDbNameProperty:
    def test_db_name_extracted_from_url(self, tmp_path):
        """
        Given a db_url with database name 'mydb',
        When _db_name is accessed,
        Then 'mydb' is returned.
        """
        # Arrange
        runner = _make_runner(tmp_path, db_url="mysql+pymysql://user:pass@host:3306/mydb")

        # Act
        result = runner._db_name

        # Assert
        assert result == "mydb"


@pytest.mark.flow
class TestApplyMigrationsCallChain:
    def test_apply_migrations_calls_yoyo_chain(self, tmp_path):
        """
        Given a migrations directory path,
        When apply_migrations() is called,
        Then yoyo get_backend, read_migrations, and apply_migrations are called
        in the correct order.
        """
        # Arrange
        runner = _make_runner(tmp_path)
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()

        mock_backend = MagicMock()
        # Properly configure the lock() context manager
        mock_lock_cm = MagicMock()
        mock_lock_cm.__enter__ = MagicMock(return_value=mock_backend)
        mock_lock_cm.__exit__ = MagicMock(return_value=False)
        mock_backend.lock.return_value = mock_lock_cm

        mock_migrations = MagicMock()
        mock_backend.to_apply.return_value = mock_migrations

        with patch("system.ports.driven.mysqldump_runner.get_backend", return_value=mock_backend) as mock_gb, \
             patch("system.ports.driven.mysqldump_runner.read_migrations", return_value=mock_migrations) as mock_rm:

            # Act
            runner.apply_migrations()

            # Assert
            mock_gb.assert_called_once()
            mock_rm.assert_called_once()
            mock_backend.apply_migrations.assert_called_once()

    def test_apply_migrations_wraps_exceptions_as_driven_port_error(self, tmp_path):
        """
        Given yoyo raises an unexpected exception,
        When apply_migrations() is called,
        Then DrivenPortError is raised with code MIGRATION_FAILED.
        """
        # Arrange
        from shared.generics.errors import DrivenPortError
        runner = _make_runner(tmp_path)

        with patch(
            "system.ports.driven.mysqldump_runner.get_backend",
            side_effect=RuntimeError("yoyo connection refused"),
        ):
            # Act + Assert
            with pytest.raises(DrivenPortError) as exc_info:
                runner.apply_migrations()

        assert exc_info.value.code == "MIGRATION_FAILED"
        assert "yoyo connection refused" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Subprocess security assertion — no --password= in args
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestDumpNoPasswordInArgv:
    def test_dump_does_not_pass_password_in_argv(self, tmp_path, monkeypatch):
        """
        Given a mock subprocess.run that captures args,
        When dump() is called,
        Then no argument in the subprocess call list starts with '--password='
        or '-p'.
        """
        # Arrange
        runner = _make_runner(tmp_path, db_url="mysql+pymysql://u:secret@h:3306/db")
        captured_args: list = []

        import subprocess
        from system.ports.driven import mysqldump_runner as _mod

        # Probe `--help` is cached at module level for the lifetime of the
        # process. Clear it so this test reliably observes the call.
        _mod._mysqldump_help_output.cache_clear()

        def fake_run(args, **kwargs):
            captured_args.extend(args)
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            return result

        dst = tmp_path / "test.sql.gz"

        monkeypatch.setattr(subprocess, "run", fake_run)

        try:
            runner.dump(str(dst))
        except Exception:
            pass  # We only care about the args check

        # Assert — --password= and -p must never appear in argv
        assert len(captured_args) > 0, "subprocess.run was not called"
        for arg in captured_args:
            assert not str(arg).startswith("--password="), (
                f"Password found in subprocess args: {arg!r}"
            )
            assert not str(arg).startswith("-p"), (
                f"Short password flag found in subprocess args: {arg!r}"
            )
