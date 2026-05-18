import re
from dataclasses import dataclass
from datetime import datetime, timezone

from ...domain.backup_errors import SnapshotMissingAfterDumpError, SnapshotNameInvalidError
from ...domain.snapshot_vo import SnapshotInfo
from ..interfaces.i_snapshot_storage import ISnapshotStorage
from ..interfaces.i_backup_runner import IBackupRunner

_PREFIX_RE = re.compile(r"[a-z\-]*")


def _build_name(prefix: str) -> str:
    if "/" in prefix or ".." in prefix or not _PREFIX_RE.fullmatch(prefix):
        raise SnapshotNameInvalidError(
            prefix,
            "prefix must match [a-z\\-]* and must not contain '/' or '..'",
        )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    return f"{prefix}{ts}.sql.gz"


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateSnapshotUseCase:
    _storage: ISnapshotStorage
    _runner: IBackupRunner

    def __call__(self, *, prefix: str = "") -> SnapshotInfo:
        name = _build_name(prefix)
        dst = self._storage.path_of(name)
        self._runner.dump(dst)
        self._storage.rotate(keep=10)
        info = self._storage.info(name)
        if info is None:
            raise SnapshotMissingAfterDumpError(name)
        return info
