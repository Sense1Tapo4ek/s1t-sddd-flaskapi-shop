from typing import Protocol, runtime_checkable

from ...domain import StorageSettings


@runtime_checkable
class IStorageSettingsRepo(Protocol):
    """
    Repository interface for StorageSettings (singleton, id=1).
    """

    def get(self) -> StorageSettings | None: ...

    def save(self, settings: StorageSettings) -> None:
        """Persist the aggregate state."""
        ...
