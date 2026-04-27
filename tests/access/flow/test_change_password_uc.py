from datetime import datetime, timedelta, timezone

import pytest

from access.app.commands import ChangePasswordCommand
from access.app.use_cases.change_password_uc import ChangePasswordUseCase
from access.app.use_cases.verify_recovery_code_uc import VerifyRecoveryCodeUseCase
from access.config import AccessConfig
from access.domain import (
    InvalidPasswordError,
    PasswordConfirmationRequiredError,
    User,
    WeakPasswordError,
)
from shared.helpers.security import hash_password, verify_password


class FakeAdminRepo:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = {user.id: user for user in users or []}
        self.password_updates: list[tuple[int, str, datetime | None]] = []

    def get_by_login(self, login: str) -> User | None:
        return next((user for user in self.users.values() if user.login == login), None)

    def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def update_password(
        self,
        user_id: int,
        password_hash: str,
        password_changed_at: datetime | None = None,
    ) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        self.password_updates.append((user_id, password_hash, password_changed_at))
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


def make_user(*, password: str = "old-password") -> User:
    return User(
        id=1,
        login="admin",
        password_hash=hash_password(password),
        role="owner",
        telegram_chat_id="tg-1",
    )


def make_config() -> AccessConfig:
    return AccessConfig(
        jwt_secret="change-password-flow-secret-with-at-least-32-bytes",
        recovery_code_ttl_minutes=5,
        recovery_code_cooldown_seconds=60,
        recovery_code_max_attempts=3,
        recovery_code_lockout_minutes=15,
    )


def make_use_case(repo: FakeAdminRepo) -> ChangePasswordUseCase:
    verify_code_uc = VerifyRecoveryCodeUseCase(_repo=repo, _config=make_config())
    return ChangePasswordUseCase(_repo=repo, _verify_code_uc=verify_code_uc)


@pytest.mark.flow
class TestChangePasswordUseCase:
    def test_weak_password_is_rejected_before_write(self) -> None:
        """
        Given an admin with a valid current password,
        When the requested new password is too short,
        Then the use case rejects it and does not update the password hash.
        """
        # Arrange
        user = make_user()
        repo = FakeAdminRepo([user])
        use_case = make_use_case(repo)

        # Act
        with pytest.raises(WeakPasswordError) as exc_info:
            use_case(
                ChangePasswordCommand(
                    admin_id=1,
                    old_password="old-password",
                    new_password="1234",
                )
            )

        # Assert
        assert exc_info.value.code == "WEAK_PASSWORD"
        assert repo.password_updates == []
        assert verify_password("old-password", user.password_hash)

    def test_weak_password_does_not_consume_confirmation_code(self) -> None:
        """
        Given an admin with a valid Telegram recovery code,
        When the requested new password is too short,
        Then the use case rejects it before consuming the code.
        """
        # Arrange
        user = make_user()
        user.recovery_code_hash = hash_password("654321")
        user.recovery_code_expires = datetime.now(timezone.utc) + timedelta(minutes=5)
        repo = FakeAdminRepo([user])
        use_case = make_use_case(repo)

        # Act
        with pytest.raises(WeakPasswordError) as exc_info:
            use_case(
                ChangePasswordCommand(
                    admin_id=1,
                    confirmation_code="654321",
                    new_password="1234",
                )
            )

        # Assert
        assert exc_info.value.code == "WEAK_PASSWORD"
        assert repo.password_updates == []
        assert user.recovery_code_hash is not None
        assert user.recovery_code_expires is not None

    def test_missing_old_password_and_code_requires_confirmation(self) -> None:
        """
        Given an admin changing to a strong password,
        When neither current password nor Telegram code is provided,
        Then the use case requires an explicit confirmation factor.
        """
        # Arrange
        repo = FakeAdminRepo([make_user()])
        use_case = make_use_case(repo)

        # Act
        with pytest.raises(PasswordConfirmationRequiredError) as exc_info:
            use_case(ChangePasswordCommand(admin_id=1, new_password="new-password"))

        # Assert
        assert exc_info.value.code == "PASSWORD_CONFIRMATION_REQUIRED"
        assert repo.password_updates == []

    def test_wrong_old_password_raises_invalid_password(self) -> None:
        """
        Given an admin changing to a strong password,
        When the supplied current password is wrong,
        Then the use case rejects the change with InvalidPasswordError.
        """
        # Arrange
        repo = FakeAdminRepo([make_user()])
        use_case = make_use_case(repo)

        # Act
        with pytest.raises(InvalidPasswordError) as exc_info:
            use_case(
                ChangePasswordCommand(
                    admin_id=1,
                    old_password="wrong-password",
                    new_password="new-password",
                )
            )

        # Assert
        assert exc_info.value.code == "INVALID_PASSWORD"
        assert repo.password_updates == []

    def test_correct_old_password_updates_password_hash(self) -> None:
        """
        Given an admin with a valid current password,
        When the current password confirms the change,
        Then the stored password hash is replaced with a hash of the new password.
        """
        # Arrange
        user = make_user()
        repo = FakeAdminRepo([user])
        use_case = make_use_case(repo)

        # Act
        use_case(
            ChangePasswordCommand(
                admin_id=1,
                old_password="old-password",
                new_password="new-password",
            )
        )

        # Assert
        assert len(repo.password_updates) == 1
        assert repo.password_updates[0][2] is not None
        assert user.password_changed_at is repo.password_updates[0][2]
        assert verify_password("new-password", user.password_hash)
        assert not verify_password("old-password", user.password_hash)

    def test_valid_telegram_code_updates_password_without_old_password(self) -> None:
        """
        Given an admin with a valid Telegram recovery code,
        When the code confirms a password change without the current password,
        Then the password hash is updated and the one-time code is consumed.
        """
        # Arrange
        user = make_user()
        user.recovery_code_hash = hash_password("654321")
        user.recovery_code_expires = datetime.now(timezone.utc) + timedelta(minutes=5)
        repo = FakeAdminRepo([user])
        use_case = make_use_case(repo)

        # Act
        use_case(
            ChangePasswordCommand(
                admin_id=1,
                confirmation_code="654321",
                new_password="new-password",
            )
        )

        # Assert
        assert len(repo.password_updates) == 1
        assert user.password_changed_at is not None
        assert verify_password("new-password", user.password_hash)
        assert user.recovery_code_hash is None
        assert user.recovery_code_expires is None
