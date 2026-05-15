import os

import pytest

from shared.adapters.driven import LocalFileStorage, S3FileStorage
from system.adapters.driven import StorageRouter
from system.domain import StorageSettings


pytestmark = pytest.mark.flow


class _Repo:
    def __init__(self, settings: StorageSettings | None) -> None:
        self.settings = settings
        self.calls = 0

    def get(self) -> StorageSettings | None:
        self.calls += 1
        return self.settings

    def save(self, s: StorageSettings) -> None:
        self.settings = s


def _local_settings() -> StorageSettings:
    return StorageSettings(id=1, backend="local")


def _s3_settings() -> StorageSettings:
    return StorageSettings(
        id=1,
        backend="s3",
        endpoint_url="https://s3.amazonaws.com",
        region="us-east-1",
        bucket="bucket",
        access_key_id="AKIA",
        secret_access_key="secret",
        public_base_url="https://bucket.s3.amazonaws.com",
    )


@pytest.fixture
def fallback_dir(tmp_path):
    path = tmp_path / "uploads"
    path.mkdir()
    return str(path)


class TestStorageRouterResolution:
    def test_local_backend_resolves_to_local_file_storage(self, fallback_dir):
        """
        Given storage settings with backend=local,
        When resolving the active backend,
        Then a LocalFileStorage instance is returned.
        """
        # Arrange
        repo = _Repo(_local_settings())
        router = StorageRouter(_settings_repo=repo, _local_fallback_dir=fallback_dir)

        # Act
        backend = router._resolve()

        # Assert
        assert isinstance(backend, LocalFileStorage)

    def test_s3_backend_resolves_to_s3_file_storage(self, fallback_dir):
        """
        Given storage settings with a complete s3 configuration,
        When resolving,
        Then an S3FileStorage instance is returned.
        """
        # Arrange
        repo = _Repo(_s3_settings())
        router = StorageRouter(_settings_repo=repo, _local_fallback_dir=fallback_dir)

        # Act
        backend = router._resolve()

        # Assert
        assert isinstance(backend, S3FileStorage)

    def test_missing_settings_falls_back_to_local(self, fallback_dir):
        """
        Given the storage_settings repo returns None,
        When resolving,
        Then the router falls back to LocalFileStorage on the configured dir.
        """
        # Arrange
        repo = _Repo(None)
        router = StorageRouter(_settings_repo=repo, _local_fallback_dir=fallback_dir)

        # Act
        backend = router._resolve()

        # Assert
        assert isinstance(backend, LocalFileStorage)


class TestStorageRouterCache:
    def test_cache_hit_within_ttl(self, fallback_dir):
        """
        Given consecutive resolves within the TTL,
        When calling _resolve repeatedly,
        Then the repo is hit only once and the same backend instance is returned.
        """
        # Arrange
        repo = _Repo(_local_settings())
        router = StorageRouter(
            _settings_repo=repo, _local_fallback_dir=fallback_dir, _ttl_seconds=10.0
        )

        # Act
        b1 = router._resolve()
        b2 = router._resolve()
        b3 = router._resolve()

        # Assert
        assert b1 is b2 is b3
        assert repo.calls == 1

    def test_invalidate_cache_forces_reresolution(self, fallback_dir):
        """
        Given a cached backend,
        When invalidate_cache() is called,
        Then the next call rebuilds the backend from fresh settings.
        """
        # Arrange
        repo = _Repo(_local_settings())
        router = StorageRouter(_settings_repo=repo, _local_fallback_dir=fallback_dir)
        b1 = router._resolve()

        # Act
        router.invalidate_cache()
        # Caller switched mode in the meantime
        repo.settings = _s3_settings()
        b2 = router._resolve()

        # Assert
        assert isinstance(b1, LocalFileStorage)
        assert isinstance(b2, S3FileStorage)
        assert repo.calls == 2

    def test_save_delegates_to_resolved_backend(self, fallback_dir):
        """
        Given backend=local,
        When calling router.save(),
        Then the file is written via LocalFileStorage and a /media/products/... path is returned.
        """
        # Arrange
        repo = _Repo(_local_settings())
        router = StorageRouter(_settings_repo=repo, _local_fallback_dir=fallback_dir)

        # Act
        url = router.save("photo.jpg", b"\x00\x01")

        # Assert
        assert url.startswith("/media/products/")
        files = os.listdir(fallback_dir)
        assert len(files) == 1
        assert files[0].endswith(".jpg")
