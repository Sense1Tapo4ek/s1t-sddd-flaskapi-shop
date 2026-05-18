from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotInfo:
    name: str
    size_bytes: int
    created_at: datetime
    mig_version: int
    is_pre_restore: bool

    @property
    def display_name(self) -> str:
        return self.name.removesuffix(".sql.gz")
