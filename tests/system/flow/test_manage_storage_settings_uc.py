import pytest

from system.app import (
    ManageStorageSettingsUseCase,
    S3ConnectionError,
    UpdateStorageSettingsCommand,
)
from system.domain import (
    IncompleteS3SettingsError,
    StorageSettings,
    StorageSettingsNotFoundError,
)


pytestmark = pytest.mark.flow


class _FakeRepo:
    def __init__(self, settings: StorageSettings | None) -> None:
        self.settings = settings
        self.save_calls = 0

    def get(self) -> StorageSettings | None:
        return self.settings

    def save(self, s: StorageSettings) -> None:
        self.save_calls += 1
        self.settings = s


class _FakeChecker:
    def __init__(self, raise_with: Exception | None = None) -> None:
        self.calls: list[StorageSettings] = []
        self._raise = raise_with

    def check(self, s: StorageSettings) -> None:
        self.calls.append(s)
        if self._raise is not None:
            raise self._raise


class _FakeInvalidator:
    def __init__(self) -> None:
        self.calls = 0

    def invalidate_cache(self) -> None:
        self.calls += 1


def _filled_s3() -> StorageSettings:
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


class TestManageStorageSettingsUseCase:
    def test_missing_aggregate_raises_not_found(self):
        """
        Given the repo has no row,
        When invoking the use case,
        Then StorageSettingsNotFoundError is raised before any side effect.
        """
        # Arrange
        repo, checker, inv = _FakeRepo(None), _FakeChecker(), _FakeInvalidator()
        uc = ManageStorageSettingsUseCase(
            _repo=repo, _health_checker=checker, _cache_invalidator=inv
        )

        # Act / Assert
        with pytest.raises(StorageSettingsNotFoundError):
            uc(UpdateStorageSettingsCommand(backend="local"))
        assert repo.save_calls == 0
        assert inv.calls == 0
        assert checker.calls == []

    def test_partial_update_keeps_existing_secret(self):
        """
        Given an existing s3 configuration with a secret,
        When updating only the bucket (secret_access_key=None),
        Then the previous secret is preserved.
        """
        # Arrange
        repo = _FakeRepo(_filled_s3())
        uc = ManageStorageSettingsUseCase(
            _repo=repo,
            _health_checker=_FakeChecker(),
            _cache_invalidator=_FakeInvalidator(),
        )

        # Act
        result = uc(UpdateStorageSettingsCommand(bucket="new-bucket"))

        # Assert
        assert result.bucket == "new-bucket"
        assert result.secret_access_key == "secret"

    def test_empty_secret_clears_existing_when_backend_is_local(self):
        """
        Given an existing s3 configuration with secret stored,
        When switching back to local AND clearing the secret in one update,
        Then both transitions are persisted (no s3 invariant applies in local mode).
        """
        # Arrange
        repo = _FakeRepo(_filled_s3())
        uc = ManageStorageSettingsUseCase(
            _repo=repo,
            _health_checker=_FakeChecker(),
            _cache_invalidator=_FakeInvalidator(),
        )

        # Act
        result = uc(UpdateStorageSettingsCommand(backend="local", secret_access_key=""))

        # Assert
        assert result.backend == "local"
        assert result.secret_access_key == ""

    def test_clearing_secret_on_active_s3_is_blocked_by_invariant(self):
        """
        Given an active s3 configuration,
        When attempting to clear the secret without switching backend,
        Then IncompleteS3SettingsError protects the system from saving a broken state.
        """
        # Arrange
        repo = _FakeRepo(_filled_s3())
        uc = ManageStorageSettingsUseCase(
            _repo=repo,
            _health_checker=_FakeChecker(),
            _cache_invalidator=_FakeInvalidator(),
        )

        # Act / Assert
        with pytest.raises(IncompleteS3SettingsError):
            uc(UpdateStorageSettingsCommand(secret_access_key=""))
        assert repo.save_calls == 0

    def test_health_check_runs_only_for_s3_with_explicit_flag(self):
        """
        Given backend stays local,
        When test_connection=True,
        Then the health checker is NOT called.
        """
        # Arrange
        repo = _FakeRepo(StorageSettings(id=1, backend="local"))
        checker = _FakeChecker()
        uc = ManageStorageSettingsUseCase(
            _repo=repo,
            _health_checker=checker,
            _cache_invalidator=_FakeInvalidator(),
        )

        # Act
        uc(UpdateStorageSettingsCommand(test_connection=True))

        # Assert
        assert checker.calls == []

    def test_health_check_runs_for_s3_when_flag_set(self):
        """
        Given a complete s3 configuration update,
        When test_connection=True,
        Then the health checker is called once before save.
        """
        # Arrange
        repo = _FakeRepo(_filled_s3())
        checker = _FakeChecker()
        inv = _FakeInvalidator()
        uc = ManageStorageSettingsUseCase(
            _repo=repo, _health_checker=checker, _cache_invalidator=inv
        )

        # Act
        uc(UpdateStorageSettingsCommand(test_connection=True))

        # Assert
        assert len(checker.calls) == 1
        assert repo.save_calls == 1
        assert inv.calls == 1

    def test_health_check_failure_blocks_save_and_invalidate(self):
        """
        Given the health checker rejects the configuration,
        When invoking the use case,
        Then settings are NOT saved and the cache is NOT invalidated.
        """
        # Arrange
        repo = _FakeRepo(_filled_s3())
        checker = _FakeChecker(raise_with=S3ConnectionError(detail="403"))
        inv = _FakeInvalidator()
        uc = ManageStorageSettingsUseCase(
            _repo=repo, _health_checker=checker, _cache_invalidator=inv
        )

        # Act / Assert
        with pytest.raises(S3ConnectionError):
            uc(UpdateStorageSettingsCommand(test_connection=True))
        assert repo.save_calls == 0
        assert inv.calls == 0

    def test_invalid_s3_invariant_blocks_save(self):
        """
        Given switching to s3 with missing required fields,
        When invoking the use case,
        Then IncompleteS3SettingsError is raised before health check or save.
        """
        # Arrange
        repo = _FakeRepo(StorageSettings(id=1, backend="local"))
        checker = _FakeChecker()
        inv = _FakeInvalidator()
        uc = ManageStorageSettingsUseCase(
            _repo=repo, _health_checker=checker, _cache_invalidator=inv
        )

        # Act / Assert
        with pytest.raises(IncompleteS3SettingsError):
            uc(UpdateStorageSettingsCommand(backend="s3", test_connection=True))
        assert repo.save_calls == 0
        assert checker.calls == []
        assert inv.calls == 0

    def test_invalidator_called_after_successful_save(self):
        """
        Given a successful update,
        When the use case completes,
        Then invalidator is called exactly once and AFTER save.
        """
        # Arrange
        events: list[str] = []

        class TracingRepo(_FakeRepo):
            def save(self, s: StorageSettings) -> None:
                events.append("save")
                super().save(s)

        class TracingInvalidator(_FakeInvalidator):
            def invalidate_cache(self) -> None:
                events.append("invalidate")
                super().invalidate_cache()

        repo = TracingRepo(StorageSettings(id=1, backend="local"))
        inv = TracingInvalidator()
        uc = ManageStorageSettingsUseCase(
            _repo=repo, _health_checker=_FakeChecker(), _cache_invalidator=inv
        )

        # Act
        uc(UpdateStorageSettingsCommand(endpoint_url="https://x"))

        # Assert
        assert events == ["save", "invalidate"]
