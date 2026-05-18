"""
Filesystem implementation of ISnapshotStorage.

Filename convention: [prefix-]<mig_version>-YYYYMMDDTHHMMSSZ.sql.gz
Example: 2-20260518T123045Z.sql.gz
         pre-restore-7-20260518T123045Z.sql.gz
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from system.app.interfaces.i_snapshot_storage import ISnapshotStorage
from system.domain.backup_errors import SnapshotNameInvalidError, SnapshotNotFoundError
from system.domain.snapshot_vo import SnapshotInfo

# Only these characters are safe in a snapshot filename.
_VALID_NAME_RE = re.compile(r'^[A-Za-z0-9._-]+\.sql\.gz$')


@dataclass(frozen=True, slots=True, kw_only=True)
class FsSnapshotStorage:
    """Read/write access to .sql.gz snapshot files on the local filesystem."""

    _dumps_dir: Path

    # ------------------------------------------------------------------
    # ISnapshotStorage
    # ------------------------------------------------------------------

    def list(self) -> list[SnapshotInfo]:
        """Return all .sql.gz snapshots, newest first."""
        paths = sorted(
            self._dumps_dir.glob("*.sql.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [self._info(p) for p in paths]

    def info(self, name: str) -> SnapshotInfo | None:
        """Return SnapshotInfo for *name* if the file exists, else None."""
        try:
            self._validate_name(name)
        except SnapshotNameInvalidError:
            return None
        path = self._dumps_dir / name
        if not path.exists():
            return None
        return self._info(path)

    def path_of(self, name: str) -> str:
        """
        Validate *name* and return its absolute path under dumps_dir.

        Raises SnapshotNameInvalidError on path-traversal attempts or
        invalid characters.
        """
        self._validate_name(name)
        return str(self._dumps_dir / name)

    def delete(self, name: str) -> None:
        """
        Delete snapshot *name*.

        Raises SnapshotNameInvalidError on invalid/traversal names.
        Raises SnapshotNotFoundError if the file does not exist.
        """
        self._validate_name(name)
        path = self._dumps_dir / name
        try:
            path.unlink(missing_ok=False)
        except FileNotFoundError:
            raise SnapshotNotFoundError(name)

    def rotate(self, keep: int) -> int:
        """
        Delete oldest non-pre-restore snapshots, keeping *keep* newest.

        Pre-restore snapshots are safety nets and are never rotated here.
        Returns the count of files deleted.
        """
        all_regular = sorted(
            (p for p in self._dumps_dir.glob("*.sql.gz")
             if not p.name.startswith("pre-restore-")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # newest first
        )
        to_delete = all_regular[keep:]
        for p in to_delete:
            p.unlink(missing_ok=True)
        return len(to_delete)

    def available_bytes(self) -> int:
        """Return free bytes available on the filesystem housing dumps_dir."""
        stat = os.statvfs(self._dumps_dir)
        return stat.f_bavail * stat.f_frsize

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_name(self, name: str) -> None:
        """Raise SnapshotNameInvalidError if *name* is not a safe filename."""
        if ".." in name:
            raise SnapshotNameInvalidError(name, "contains '..' (path traversal)")
        if "/" in name:
            raise SnapshotNameInvalidError(name, "contains '/' (path separator)")
        if not _VALID_NAME_RE.match(name):
            raise SnapshotNameInvalidError(
                name,
                "must match [A-Za-z0-9._-]+\\.sql\\.gz",
            )

    def _info(self, path: Path) -> SnapshotInfo:
        """Build a SnapshotInfo from a .sql.gz file path."""
        name = path.name
        stat = path.stat()

        # Parse mig_version: strip optional 'pre-restore-' prefix, then
        # take the leading numeric segment before the first '-'.
        stem = name.removeprefix("pre-restore-")
        is_pre_restore = name.startswith("pre-restore-")

        try:
            mig_version = int(stem.split("-")[0])
        except (ValueError, IndexError):
            mig_version = 0

        return SnapshotInfo(
            name=name,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            mig_version=mig_version,
            is_pre_restore=is_pre_restore,
        )
