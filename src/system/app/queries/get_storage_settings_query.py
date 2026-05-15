from dataclasses import dataclass

from ...domain import StorageSettings, StorageSettingsNotFoundError
from ..interfaces import IStorageSettingsRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class GetStorageSettingsQuery:
    _repo: IStorageSettingsRepo

    def __call__(self) -> StorageSettings:
        settings = self._repo.get()
        if settings is None:
            raise StorageSettingsNotFoundError()
        return settings
