"""
Subprocess-based implementation of IBackupRunner.

Security invariants:
- Credentials are NEVER passed as CLI arguments (--password= or -p).
  They are written to a temp file created via mkstemp (0o600 by POSIX
  guarantee) and passed via --defaults-extra-file.
- The temp creds file is always deleted in a finally block via
  Path.unlink(missing_ok=True) so cleanup never raises FileNotFoundError
  and buries the real cause.
"""
from __future__ import annotations

import gzip
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.engine.url import make_url
from yoyo import get_backend, read_migrations

from shared.generics.errors import DrivenPortError
from system.app.interfaces.i_backup_runner import IBackupRunner


@dataclass(frozen=True, slots=True, kw_only=True)
class MysqldumpRunner:
    """
    Implements IBackupRunner using the local mysqldump / mysql binaries.

    All subprocess calls use --defaults-extra-file instead of --password=
    to avoid exposing credentials in the process list or shell history.
    """

    _db_url: str
    _engine: Engine
    _mysqldump_bin: str = "mysqldump"
    _mysql_bin: str = "mysql"
    _restart_file: Path = field(default_factory=lambda: Path("tmp/restart.txt"))
    _migrations_dir: Path = field(default_factory=lambda: Path("migrations"))

    # ------------------------------------------------------------------
    # IBackupRunner
    # ------------------------------------------------------------------

    def dump(self, dst_path: str) -> int:
        """
        Run mysqldump and compress output into *dst_path* (.sql.gz).

        Returns the byte size of the resulting file.
        Raises DrivenPortError on subprocess failure.
        """
        creds_file = self._write_defaults_file()
        try:
            with gzip.open(dst_path, "wb") as out_fd:
                try:
                    subprocess.run(
                        [
                            self._mysqldump_bin,
                            f"--defaults-extra-file={creds_file}",
                            "--single-transaction",
                            "--quick",
                            "--skip-column-statistics",
                            self._db_name,
                        ],
                        check=True,
                        stdout=out_fd,
                        stderr=subprocess.PIPE,
                    )
                except subprocess.CalledProcessError as e:
                    raise DrivenPortError(
                        f"mysqldump failed (rc={e.returncode}): "
                        f"{e.stderr.decode(errors='replace')[:500]}",
                        code="DUMP_FAILED",
                    ) from e
        finally:
            Path(creds_file).unlink(missing_ok=True)

        return Path(dst_path).stat().st_size

    def restore(self, src_path: str) -> None:
        """
        Decompress *src_path* (.sql.gz) and pipe into the mysql client.

        Raises DrivenPortError on subprocess failure.
        """
        creds_file = self._write_defaults_file()
        try:
            cmd = [
                self._mysql_bin,
                f"--defaults-extra-file={creds_file}",
                self._db_name,
            ]
            with gzip.open(src_path, "rb") as gz_in:
                result = subprocess.run(
                    cmd,
                    stdin=gz_in,
                    capture_output=True,
                )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace")
                raise DrivenPortError(
                    f"mysql exited with code {result.returncode}: {stderr[:500]}",
                    code="RESTORE_FAILED",
                )
        finally:
            Path(creds_file).unlink(missing_ok=True)

    def apply_migrations(self) -> None:
        """Apply pending yoyo migrations programmatically."""
        try:
            backend = get_backend(self._db_url)
            migrations = read_migrations(str(self._migrations_dir))
            with backend.lock():
                backend.apply_migrations(backend.to_apply(migrations))
        except Exception as exc:
            raise DrivenPortError(
                f"Migration failed: {exc}",
                code="MIGRATION_FAILED",
            ) from exc

    def dispose_pool(self) -> None:
        """Dispose the SQLAlchemy connection pool (used before restore)."""
        self._engine.dispose()

    def request_worker_restart(self) -> None:
        """
        Touch the Passenger restart file if its parent directory exists.

        On CPanel/Passenger, touching tmp/restart.txt triggers a worker reload.
        If the directory does not exist (e.g. local dev), this is a no-op.
        """
        if self._restart_file.parent.exists():
            self._restart_file.touch()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _db_name(self) -> str:
        """Extract the database name from the SQLAlchemy db_url."""
        url = make_url(self._db_url)
        return url.database  # type: ignore[return-value]

    def _write_defaults_file(self) -> str:
        """
        Write a MySQL [client] defaults file to a temp path with mode 0o600.

        Uses mkstemp so the file is created atomically with 0o600 permissions
        (POSIX guarantee) — no separate chmod needed.
        Credentials are parsed from the SQLAlchemy db_url.
        Returns the absolute path to the temp file.
        """
        url = make_url(self._db_url)
        host = url.host or "localhost"
        port = url.port or 3306
        user = url.username or ""
        password = url.password or ""

        content = (
            "[client]\n"
            f"host={host}\n"
            f"user={user}\n"
            f"password={password}\n"
            f"port={port}\n"
        )

        fd, path = tempfile.mkstemp(suffix=".cnf", dir=tempfile.gettempdir())
        with os.fdopen(fd, "w") as tmp:
            tmp.write(content)
        return path
