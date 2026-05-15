from dataclasses import dataclass
from typing import ClassVar, Literal

from shared.generics.errors import DomainError


StorageBackend = Literal["local", "s3"]


class InvalidStorageBackendError(DomainError):
    def __init__(self, value: str) -> None:
        super().__init__(
            message=f"Неизвестный бэкенд хранилища: {value!r}",
            code="INVALID_STORAGE_BACKEND",
        )


class IncompleteS3SettingsError(DomainError):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            message=(
                "Для режима S3 заполните обязательные поля: " + ", ".join(missing)
            ),
            code="INCOMPLETE_S3_SETTINGS",
        )


_VALID_BACKENDS: tuple[StorageBackend, ...] = ("local", "s3")


@dataclass(slots=True)
class StorageSettings:
    """
    Aggregate Root for file storage configuration.

    Singleton (id=1 in DB). Holds the active backend (`local` | `s3`)
    and the parameters required by S3 mode.
    """

    id: int
    backend: StorageBackend = "local"
    endpoint_url: str = ""
    region: str = ""
    bucket: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    public_base_url: str = ""
    force_path_style: bool = False

    _S3_REQUIRED: ClassVar[tuple[str, ...]] = (
        "bucket",
        "access_key_id",
        "secret_access_key",
        "public_base_url",
    )

    def update(self, **kwargs) -> None:
        """Apply partial updates. Only non-None values are set."""
        for key, val in kwargs.items():
            if val is None:
                continue
            if key == "backend" and val not in _VALID_BACKENDS:
                raise InvalidStorageBackendError(val)
            setattr(self, key, val)

    def validate_active_backend(self) -> None:
        """Invariant: when backend=='s3', required S3 fields must be filled."""
        if self.backend != "s3":
            return
        missing = [f for f in self._S3_REQUIRED if not getattr(self, f)]
        if missing:
            raise IncompleteS3SettingsError(missing)

    @property
    def is_s3(self) -> bool:
        return self.backend == "s3"
