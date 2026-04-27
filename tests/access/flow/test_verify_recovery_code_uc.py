from datetime import datetime, timedelta, timezone

import pytest

from access.app.use_cases.verify_recovery_code_uc import (
    InvalidRecoveryCodeError,
    VerifyRecoveryCodeUseCase,
)
from access.config import AccessConfig
from access.domain import AdminInactiveError, RecoveryCodeLockedError, User
from shared.helpers.security import hash_password, verify_jwt


class FakeAdminRepo:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = {user.id: user for user in users or []}
        self.clear_calls: list[int] = []
        self.record_failure_calls: list[tuple[int, int, datetime | None]] = []

    def get_by_login(self, login: str) -> User | None:
        return next((user for user in self.users.values() if user.login == login), None)

    def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def update_password(self, user_id: int, password_hash: str, password_changed_at=None) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        user.password_hash = password_hash
        user.password_changed_at = password_changed_at
        return user

    def update_telegram_chat_id(
        self,
        user_id: int,
        chat_id: str | None,
    ) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        user.telegram_chat_id = chat_id or None
        return user

    def set_recovery_code(self, user_id: int, code_hash: str, expires) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        user.recovery_code_hash = code_hash
        user.recovery_code_expires = expires
        user.recovery_code_attempts = 0
        user.recovery_code_last_sent_at = datetime.now(expires.tzinfo)
        user.recovery_code_locked_until = None

    def record_recovery_failure(
        self,
        user_id: int,
        attempts: int,
        locked_until,
    ) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        self.record_failure_calls.append((user_id, attempts, locked_until))
        user.recovery_code_attempts = attempts
        user.recovery_code_locked_until = locked_until

    def clear_recovery_code(self, user_id: int) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        self.clear_calls.append(user_id)
        user.recovery_code_hash = None
        user.recovery_code_expires = None
        user.recovery_code_attempts = 0
        user.recovery_code_locked_until = None


def make_user(
    *,
    user_id: int = 1,
    login: str = "admin",
    is_active: bool = True,
    recovery_code: str | None = "123456",
    expires: datetime | None = None,
    attempts: int = 0,
    locked_until: datetime | None = None,
) -> User:
    if expires is None and recovery_code is not None:
        expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    return User(
        id=user_id,
        login=login,
        password_hash=hash_password("password"),
        role="owner",
        is_active=is_active,
        recovery_code_hash=(
            hash_password(recovery_code) if recovery_code is not None else None
        ),
        recovery_code_expires=expires,
        recovery_code_attempts=attempts,
        recovery_code_locked_until=locked_until,
    )


def make_config() -> AccessConfig:
    return AccessConfig(
        jwt_secret="verify-recovery-code-flow-secret-with-at-least-32-bytes",
        recovery_code_ttl_minutes=5,
        recovery_code_cooldown_seconds=60,
        recovery_code_max_attempts=3,
        recovery_code_lockout_minutes=15,
    )


@pytest.mark.flow
class TestVerifyRecoveryCodeUseCase:
    def test_missing_code_is_rejected_without_recording_attempt(self) -> None:
        """
        Given an admin without a stored recovery code,
        When a code verification is attempted,
        Then the use case rejects it without recording a failed attempt.
        """
        # Arrange
        repo = FakeAdminRepo([make_user(recovery_code=None)])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(InvalidRecoveryCodeError) as exc_info:
            use_case("123456", admin_id=1)

        # Assert
        assert exc_info.value.code == "INVALID_RECOVERY_CODE"
        assert repo.record_failure_calls == []
        assert repo.clear_calls == []

    def test_expired_code_is_rejected_and_cleared(self) -> None:
        """
        Given an admin with an expired recovery code,
        When that code is verified,
        Then verification fails and the expired code is cleared.
        """
        # Arrange
        user = make_user(expires=datetime.now(timezone.utc) - timedelta(seconds=1))
        repo = FakeAdminRepo([user])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(InvalidRecoveryCodeError) as exc_info:
            use_case("123456", admin_id=1)

        # Assert
        assert exc_info.value.code == "INVALID_RECOVERY_CODE"
        assert repo.clear_calls == [1]
        assert user.recovery_code_hash is None
        assert user.recovery_code_expires is None

    def test_wrong_code_increments_attempts(self) -> None:
        """
        Given an admin with a valid unexpired recovery code,
        When a wrong code is verified below the attempt limit,
        Then the failed attempt count is incremented without locking.
        """
        # Arrange
        user = make_user()
        repo = FakeAdminRepo([user])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(InvalidRecoveryCodeError) as exc_info:
            use_case("000000", admin_id=1)

        # Assert
        assert exc_info.value.code == "INVALID_RECOVERY_CODE"
        assert repo.record_failure_calls == [(1, 1, None)]
        assert user.recovery_code_attempts == 1
        assert user.recovery_code_locked_until is None
        assert user.recovery_code_hash is not None

    def test_max_attempts_locks_and_raises_locked_error(self) -> None:
        """
        Given an admin one failed attempt away from the limit,
        When another wrong recovery code is verified,
        Then the code flow is locked and RecoveryCodeLockedError is raised.
        """
        # Arrange
        config = make_config()
        user = make_user(attempts=config.recovery_code_max_attempts - 1)
        repo = FakeAdminRepo([user])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=config)
        before = datetime.now(timezone.utc)

        # Act
        with pytest.raises(RecoveryCodeLockedError) as exc_info:
            use_case("000000", admin_id=1)
        after = datetime.now(timezone.utc)

        # Assert
        assert exc_info.value.code == "RECOVERY_CODE_LOCKED"
        assert user.recovery_code_attempts == config.recovery_code_max_attempts
        assert user.recovery_code_locked_until is not None
        assert repo.record_failure_calls == [
            (1, config.recovery_code_max_attempts, user.recovery_code_locked_until)
        ]
        assert before + timedelta(minutes=config.recovery_code_lockout_minutes) <= (
            user.recovery_code_locked_until
        )
        assert user.recovery_code_locked_until <= (
            after + timedelta(minutes=config.recovery_code_lockout_minutes)
        )

    def test_locked_code_rejects_before_verifying_attempt(self) -> None:
        """
        Given an admin whose recovery code flow is already locked,
        When any code is submitted before the lockout expires,
        Then verification is rejected without recording another attempt.
        """
        # Arrange
        user = make_user(
            attempts=2,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        repo = FakeAdminRepo([user])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(RecoveryCodeLockedError) as exc_info:
            use_case("000000", admin_id=1)

        # Assert
        assert exc_info.value.code == "RECOVERY_CODE_LOCKED"
        assert user.recovery_code_attempts == 2
        assert repo.record_failure_calls == []
        assert repo.clear_calls == []

    def test_inactive_user_is_rejected_before_verifying_code(self) -> None:
        """
        Given an inactive admin with a valid recovery code,
        When the code is verified,
        Then the use case rejects it without consuming or recording the code.
        """
        # Arrange
        user = make_user(is_active=False)
        repo = FakeAdminRepo([user])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(AdminInactiveError) as exc_info:
            use_case("123456", admin_id=1)

        # Assert
        assert exc_info.value.code == "ADMIN_INACTIVE"
        assert repo.clear_calls == []
        assert repo.record_failure_calls == []
        assert user.recovery_code_hash is not None

    def test_valid_code_clears_code_and_returns_token(self) -> None:
        """
        Given an admin with a valid recovery code,
        When the code is verified for login,
        Then the code is cleared and a JWT for the admin is returned.
        """
        # Arrange
        config = make_config()
        user = make_user()
        repo = FakeAdminRepo([user])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=config)

        # Act
        before = datetime.now(timezone.utc)
        token = use_case(
            "123456",
            admin_id=1,
            remember_me=True,
            csrf_token="csrf-token-1",
        )
        after = datetime.now(timezone.utc)

        # Assert
        payload = verify_jwt(token, config.jwt_secret)
        assert payload is not None
        assert payload["sub"] == 1
        assert payload["login"] == "admin"
        assert payload["csrf"] == "csrf-token-1"
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert before + timedelta(days=30, seconds=-2) <= expires_at
        assert expires_at <= after + timedelta(days=30)
        assert repo.clear_calls == [1]
        assert user.recovery_code_hash is None
        assert user.recovery_code_expires is None

    def test_for_login_verifies_code_for_the_named_user(self) -> None:
        """
        Given two admins with different recovery codes,
        When verifying a Telegram login code by login,
        Then the code is checked against the named user and only that code is cleared.
        """
        # Arrange
        config = make_config()
        admin = make_user(user_id=1, login="admin", recovery_code="123456")
        owner = make_user(user_id=2, login="owner", recovery_code="654321")
        repo = FakeAdminRepo([admin, owner])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=config)

        # Act
        token = use_case.for_login("owner", "654321", csrf_token="csrf-owner")

        # Assert
        payload = verify_jwt(token, config.jwt_secret)
        assert payload is not None
        assert payload["sub"] == 2
        assert payload["login"] == "owner"
        assert payload["csrf"] == "csrf-owner"
        assert repo.clear_calls == [2]
        assert admin.recovery_code_hash is not None
        assert owner.recovery_code_hash is None

    def test_for_login_rejects_unknown_login(self) -> None:
        """
        Given no admin with the submitted login,
        When verifying a Telegram login code,
        Then the use case returns the generic invalid-code error.
        """
        # Arrange
        repo = FakeAdminRepo([make_user()])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(InvalidRecoveryCodeError) as exc_info:
            use_case.for_login("missing", "123456")

        # Assert
        assert exc_info.value.code == "INVALID_RECOVERY_CODE"
        assert repo.clear_calls == []
        assert repo.record_failure_calls == []

    def test_for_login_rejects_code_that_belongs_to_another_user(self) -> None:
        """
        Given two admins with different recovery codes,
        When verifying one admin's login with another admin's code,
        Then the named user's attempt is recorded and no code is cleared.
        """
        # Arrange
        admin = make_user(user_id=1, login="admin", recovery_code="123456")
        owner = make_user(user_id=2, login="owner", recovery_code="654321")
        repo = FakeAdminRepo([admin, owner])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(InvalidRecoveryCodeError) as exc_info:
            use_case.for_login("owner", "123456")

        # Assert
        assert exc_info.value.code == "INVALID_RECOVERY_CODE"
        assert repo.record_failure_calls == [(2, 1, None)]
        assert repo.clear_calls == []
        assert admin.recovery_code_hash is not None
        assert owner.recovery_code_hash is not None

    def test_verify_for_user_clears_code_without_returning_token(self) -> None:
        """
        Given an admin with a valid recovery code,
        When the code is verified as a confirmation factor for that user,
        Then the code is cleared and no login token is issued.
        """
        # Arrange
        user = make_user()
        repo = FakeAdminRepo([user])
        use_case = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        result = use_case.verify_for_user(admin_id=1, code="123456")

        # Assert
        assert result is None
        assert repo.clear_calls == [1]
        assert user.recovery_code_hash is None
        assert user.recovery_code_expires is None
