import re
from datetime import datetime, timedelta, timezone

import pytest

from access.app.use_cases.reset_password_uc import GenerateRecoveryCodeUseCase
from access.config import AccessConfig
from access.domain import (
    AdminInactiveError,
    RecoveryCodeCooldownError,
    RecoveryCodeLockedError,
    TelegramLoginUnavailableError,
    User,
)
from shared.helpers.security import hash_password, verify_password


class FakeAdminRepo:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = {user.id: user for user in users or []}
        self.set_code_calls: list[tuple[int, str, datetime]] = []

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
        self.set_code_calls.append((user_id, code_hash, expires))
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
        user.recovery_code_attempts = attempts
        user.recovery_code_locked_until = locked_until

    def clear_recovery_code(self, user_id: int) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        user.recovery_code_hash = None
        user.recovery_code_expires = None
        user.recovery_code_attempts = 0
        user.recovery_code_locked_until = None


def make_user(
    *,
    user_id: int = 1,
    login: str = "admin",
    is_active: bool = True,
    telegram_chat_id: str | None = "tg-1",
) -> User:
    return User(
        id=user_id,
        login=login,
        password_hash=hash_password("password"),
        role="owner",
        telegram_chat_id=telegram_chat_id,
        is_active=is_active,
    )


def make_config() -> AccessConfig:
    return AccessConfig(
        jwt_secret="generate-recovery-code-flow-secret-with-at-least-32-bytes",
        recovery_code_ttl_minutes=5,
        recovery_code_cooldown_seconds=60,
        recovery_code_max_attempts=3,
        recovery_code_lockout_minutes=15,
    )


@pytest.mark.flow
class TestGenerateRecoveryCodeUseCase:
    def test_inactive_user_is_rejected(self) -> None:
        """
        Given an inactive admin,
        When a recovery code is requested,
        Then the use case rejects the request without storing a code.
        """
        # Arrange
        repo = FakeAdminRepo([make_user(is_active=False)])
        use_case = GenerateRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(AdminInactiveError) as exc_info:
            use_case(admin_id=1)

        # Assert
        assert exc_info.value.code == "ADMIN_INACTIVE"
        assert repo.set_code_calls == []

    def test_cooldown_is_rejected_without_storing_new_code(self) -> None:
        """
        Given an admin who recently received a recovery code,
        When another code is requested inside the cooldown window,
        Then the request is rejected without replacing the stored code.
        """
        # Arrange
        user = make_user()
        user.recovery_code_last_sent_at = datetime.now(timezone.utc) - timedelta(
            seconds=10
        )
        repo = FakeAdminRepo([user])
        use_case = GenerateRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(RecoveryCodeCooldownError) as exc_info:
            use_case(admin_id=1)

        # Assert
        assert exc_info.value.code == "RECOVERY_CODE_COOLDOWN"
        assert repo.set_code_calls == []

    def test_lockout_is_rejected_without_storing_new_code(self) -> None:
        """
        Given an admin whose recovery code flow is locked,
        When another code is requested before the lockout expires,
        Then the use case rejects the request without storing a code.
        """
        # Arrange
        user = make_user()
        user.recovery_code_locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=10
        )
        repo = FakeAdminRepo([user])
        use_case = GenerateRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(RecoveryCodeLockedError) as exc_info:
            use_case(admin_id=1)

        # Assert
        assert exc_info.value.code == "RECOVERY_CODE_LOCKED"
        assert repo.set_code_calls == []

    @pytest.mark.parametrize(
        ("login", "user"),
        [
            ("missing", make_user(telegram_chat_id="tg-1")),
            ("admin", make_user(telegram_chat_id=None)),
            ("admin", make_user(is_active=False, telegram_chat_id="tg-1")),
        ],
    )
    def test_for_login_rejects_unknown_or_unbound_telegram_generically(
        self,
        login: str,
        user: User,
    ) -> None:
        """
        Given an unknown, inactive, or Telegram-unbound admin login,
        When a login recovery code is requested,
        Then the use case returns the generic Telegram-login unavailable error.
        """
        # Arrange
        repo = FakeAdminRepo([user])
        use_case = GenerateRecoveryCodeUseCase(_repo=repo, _config=make_config())

        # Act
        with pytest.raises(TelegramLoginUnavailableError) as exc_info:
            use_case.for_login(login)

        # Assert
        assert exc_info.value.code == "TELEGRAM_LOGIN_UNAVAILABLE"
        assert repo.set_code_calls == []

    def test_valid_request_stores_hashed_code_expiry_and_returns_six_digits(
        self,
    ) -> None:
        """
        Given an active admin outside cooldown and lockout,
        When a recovery code is generated,
        Then a six-digit code is returned and only its hash with expiry is stored.
        """
        # Arrange
        config = make_config()
        user = make_user()
        repo = FakeAdminRepo([user])
        use_case = GenerateRecoveryCodeUseCase(_repo=repo, _config=config)
        before = datetime.now(timezone.utc)

        # Act
        code = use_case(admin_id=1)

        # Assert
        after = datetime.now(timezone.utc)
        assert re.fullmatch(r"\d{6}", code)
        assert len(repo.set_code_calls) == 1
        assert user.recovery_code_hash is not None
        assert user.recovery_code_hash != code
        assert verify_password(code, user.recovery_code_hash)
        assert user.recovery_code_attempts == 0
        assert user.recovery_code_locked_until is None
        assert user.recovery_code_last_sent_at is not None
        assert user.recovery_code_expires is not None
        assert before + timedelta(minutes=config.recovery_code_ttl_minutes) <= (
            user.recovery_code_expires
        )
        assert user.recovery_code_expires <= (
            after + timedelta(minutes=config.recovery_code_ttl_minutes)
        )
