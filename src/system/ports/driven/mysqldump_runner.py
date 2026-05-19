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
import shutil
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
            # --skip-column-statistics is a MySQL 8.0+ flag (rejected by 5.7's
            # mysqldump). Probe and add it only when supported.
            cmd = [
                self._mysqldump_bin,
                f"--defaults-extra-file={creds_file}",
                "--single-transaction",
                "--quick",
                # The shop user lacks PROCESS; without this flag mysqldump
                # tries to inspect tablespaces and emits a noisy "Access
                # denied" to stderr.
                "--no-tablespaces",
            ]
            if self._supports_column_statistics_flag():
                cmd.append("--skip-column-statistics")
            cmd.append(self._db_name)

            # Stream stdout through gzip ourselves. Passing a gzip file object
            # as `stdout=` to subprocess.run uses its raw fileno() and writes
            # uncompressed bytes — the gzip wrapper then only emits its footer
            # on close, producing a corrupt .sql.gz file.
            with open(dst_path, "wb") as raw_fd, \
                 gzip.GzipFile(fileobj=raw_fd, mode="wb") as gz_out:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                try:
                    assert proc.stdout is not None
                    shutil.copyfileobj(proc.stdout, gz_out)
                finally:
                    proc.stdout.close()
                _, stderr = proc.communicate()
                if proc.returncode != 0:
                    raise DrivenPortError(
                        f"mysqldump failed (rc={proc.returncode}): "
                        f"{stderr.decode(errors='replace')[:500]}",
                        code="DUMP_FAILED",
                    )
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
                # NUL bytes may appear in BLOB columns inside the dump;
                # without binary-mode the client rejects them at parse time.
                "--binary-mode=1",
                self._db_name,
            ]
            # Decompress fully into memory and hand the SQL to mysql via
            # communicate(input=...). Passing a GzipFile object as `stdin=`
            # to subprocess uses its raw fileno() (sends the compressed
            # bytes); hand-piping via Popen + close() is brittle because
            # communicate() flushes an already-closed stdin. Snapshots are
            # small enough (≪ a few MB) to buffer.
            with gzip.open(src_path, "rb") as gz_in:
                payload = gz_in.read()
            result = subprocess.run(
                cmd,
                input=payload,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise DrivenPortError(
                    f"mysql exited with code {result.returncode}: "
                    f"{result.stderr.decode(errors='replace')[:500]}",
                    code="RESTORE_FAILED",
                )
        finally:
            Path(creds_file).unlink(missing_ok=True)

    def apply_migrations(self) -> None:
        """Apply pending yoyo migrations programmatically."""
        try:
            # yoyo recognises ``mysql://``; the project uses SQLAlchemy's
            # dialect-qualified ``mysql+pymysql://`` form. Strip the driver
            # suffix before handing the URL to yoyo.
            yoyo_url = self._db_url.replace("mysql+pymysql://", "mysql://", 1)
            backend = get_backend(yoyo_url)
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

    def _supports_column_statistics_flag(self) -> bool:
        haystack = self._mysqldump_help()
        return b"--column-statistics" in haystack

    def _client_is_mariadb(self) -> bool:
        return b"mariadb" in self._mysqldump_help().lower()

    def _mysqldump_help(self) -> bytes:
        try:
            result = subprocess.run(
                [self._mysqldump_bin, "--help"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return b""
        return result.stdout + result.stderr

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

        # The MariaDB 11 client tries TLS by default and bails on MySQL 5.7's
        # self-signed cert. Disable TLS via the dialect-specific key (MariaDB
        # rejects the foreign one as "unknown variable", so we cannot include
        # both blindly).
        if self._client_is_mariadb():
            ssl_line = "ssl=0\n"
        else:
            ssl_line = "ssl-mode=DISABLED\n"

        content = (
            "[client]\n"
            f"host={host}\n"
            f"user={user}\n"
            f"password={password}\n"
            f"port={port}\n"
            f"{ssl_line}"
        )

        fd, path = tempfile.mkstemp(suffix=".cnf", dir=tempfile.gettempdir())
        with os.fdopen(fd, "w") as tmp:
            tmp.write(content)
        return path
