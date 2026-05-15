import logging
import threading
import time
from dataclasses import dataclass, field

from shared.adapters.driven.file_storage import LocalFileStorage
from shared.adapters.driven.s3_file_storage import S3FileStorage
from system.adapters.driven.s3_client_factory import build_s3_client
from system.app.interfaces import IStorageSettingsRepo


logger = logging.getLogger(__name__)


_CACHE_TTL_SECONDS: float = 30.0


@dataclass(slots=True, kw_only=True)
class StorageRouter:
    """
    Routes IFileStorage calls to the active backend defined by StorageSettings.

    Reads settings via `IStorageSettingsRepo` and caches the resolved backend
    for `_CACHE_TTL_SECONDS` seconds. Switching mode in the admin UI takes
    effect within that TTL without an app restart; call `invalidate_cache()`
    immediately after a settings update for instant propagation.
    """

    _settings_repo: IStorageSettingsRepo
    _local_fallback_dir: str
    _ttl_seconds: float = _CACHE_TTL_SECONDS
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _backend: object | None = None  # IFileStorage; cached
    _expires_at: float = 0.0

    def save(self, filename: str, data: bytes) -> str:
        return self._resolve().save(filename, data)

    def delete(self, file_path: str) -> bool:
        return self._resolve().delete(file_path)

    def invalidate_cache(self) -> None:
        with self._lock:
            self._backend = None
            self._expires_at = 0.0

    def _resolve(self):
        now = time.monotonic()
        if self._backend is not None and self._expires_at > now:
            return self._backend

        with self._lock:
            now = time.monotonic()
            if self._backend is not None and self._expires_at > now:
                return self._backend

            settings = self._settings_repo.get()
            if settings is None or not settings.is_s3:
                if settings is None:
                    logger.warning(
                        "storage settings missing, falling back to local dir=%s",
                        self._local_fallback_dir,
                    )
                backend = LocalFileStorage(_upload_dir=self._local_fallback_dir)
            else:
                # Invariant is enforced by ManageStorageSettingsUseCase before
                # any save; we trust the persisted aggregate here.
                client = build_s3_client(settings)
                backend = S3FileStorage(
                    _client=client,
                    _bucket=settings.bucket,
                    _public_base_url=settings.public_base_url.rstrip("/"),
                )

            self._backend = backend
            self._expires_at = now + self._ttl_seconds
            return backend
