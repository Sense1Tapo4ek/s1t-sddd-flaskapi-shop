import dataclasses
from dataclasses import dataclass

from ...domain import StorageSettings, StorageSettingsNotFoundError
from ..commands import UpdateStorageSettingsCommand
from ..interfaces import (
    IS3HealthChecker,
    IStorageCacheInvalidator,
    IStorageSettingsRepo,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ManageStorageSettingsUseCase:
    """
    Updates storage settings.

    Flow:
      1. Load current aggregate (must already exist after bootstrap).
      2. Apply only provided fields. `secret_access_key=None` keeps the existing value.
      3. Validate domain invariants (S3 required fields if backend=='s3').
      4. Optionally test S3 connectivity before persisting.
      5. Persist.
      6. Invalidate the storage backend cache so the new mode takes effect now.
    """

    _repo: IStorageSettingsRepo
    _health_checker: IS3HealthChecker
    _cache_invalidator: IStorageCacheInvalidator

    def __call__(self, cmd: UpdateStorageSettingsCommand) -> StorageSettings:
        settings = self._repo.get()
        if settings is None:
            raise StorageSettingsNotFoundError()

        updates = {
            k: v
            for k, v in dataclasses.asdict(cmd).items()
            if k != "test_connection" and v is not None
        }
        settings.update(**updates)
        settings.validate_active_backend()

        if cmd.test_connection and settings.is_s3:
            self._health_checker.check(settings)

        self._repo.save(settings)
        self._cache_invalidator.invalidate_cache()
        return settings
