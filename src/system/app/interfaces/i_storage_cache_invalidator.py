from typing import Protocol, runtime_checkable


@runtime_checkable
class IStorageCacheInvalidator(Protocol):
    """
    Forces the active IFileStorage backend to be re-resolved on the next call.
    Implemented by StorageRouter; called after storage settings are updated
    so the new backend takes effect immediately instead of after the TTL.
    """

    def invalidate_cache(self) -> None: ...
