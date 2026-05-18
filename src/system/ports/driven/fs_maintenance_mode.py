"""
Filesystem implementation of IMaintenanceMode.

The flag path must match MAINTENANCE_FLAG in
shared/adapters/driving/maintenance.py (currently data/.maintenance).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from shared.generics.errors import DrivenPortError
from system.app.interfaces.i_maintenance import IMaintenanceMode

_DEFAULT_FLAG = Path("data/.maintenance")


@dataclass(frozen=True, slots=True, kw_only=True)
class FsMaintenanceMode:
    """Toggle maintenance mode by touching/removing a flag file."""

    _flag_path: Path = field(default=_DEFAULT_FLAG)

    def enter(self) -> None:
        """Create the maintenance flag file (creates parent dirs if needed)."""
        try:
            self._flag_path.parent.mkdir(parents=True, exist_ok=True)
            self._flag_path.touch(exist_ok=True)
        except OSError as exc:
            raise DrivenPortError(
                f"Maintenance flag enter failed: {exc}",
                code="MAINTENANCE_FAILED",
            ) from exc

    def exit(self) -> None:
        """Remove the maintenance flag file. Idempotent if already absent."""
        try:
            self._flag_path.unlink(missing_ok=True)
        except OSError as exc:
            raise DrivenPortError(
                f"Maintenance flag exit failed: {exc}",
                code="MAINTENANCE_FAILED",
            ) from exc
