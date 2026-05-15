from typing import Protocol, runtime_checkable

from ...domain import StorageSettings


@runtime_checkable
class IS3HealthChecker(Protocol):
    """
    Validates S3 connectivity for a given StorageSettings snapshot.
    Implementations MUST raise S3ConnectionError on failure.
    """

    def check(self, settings: StorageSettings) -> None: ...
