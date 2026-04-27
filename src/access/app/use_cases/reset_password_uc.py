import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from shared.helpers.security import hash_password
from access.config import AccessConfig
from ...domain import (
    AdminInactiveError,
    RecoveryCodeCooldownError,
    RecoveryCodeLockedError,
    TelegramLoginUnavailableError,
    User,
)
from ...domain.errors import AdminNotFoundError
from ..interfaces import IAdminRepo


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResetPasswordUseCase:
    """
    System-level password reset (triggered via ACL).
    Generates a secure temporary password.
    """

    _repo: IAdminRepo

    def __call__(self, admin_id: int = 1) -> str:
        user = self._repo.get_by_id(admin_id)
        if user is None:
            raise AdminNotFoundError(admin_id)

        new_password = secrets.token_urlsafe(8)
        new_hash = hash_password(new_password)
        self._repo.update_password(user.id, new_hash)

        return new_password


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateRecoveryCodeUseCase:
    """
    Generates a 6-digit one-time login code, stores its hash with configured expiry.
    Returns the plain code (to be sent via Telegram).
    """

    _repo: IAdminRepo
    _config: AccessConfig

    def __call__(self, admin_id: int = 1) -> str:
        user = self._repo.get_by_id(admin_id)
        if user is None:
            raise AdminNotFoundError(admin_id)
        if not user.is_active:
            raise AdminInactiveError()
        self._ensure_can_send(user)

        code = f"{secrets.randbelow(1000000):06d}"
        code_hash = hash_password(code)
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=self._config.recovery_code_ttl_minutes
        )

        self._repo.set_recovery_code(user.id, code_hash, expires)
        return code

    def _ensure_can_send(self, user: User) -> None:
        now = datetime.now(timezone.utc)
        locked_until = _as_utc(user.recovery_code_locked_until)
        if locked_until and locked_until > now:
            raise RecoveryCodeLockedError()

        last_sent_at = _as_utc(user.recovery_code_last_sent_at)
        if last_sent_at is None:
            return
        cooldown_until = last_sent_at + timedelta(
            seconds=self._config.recovery_code_cooldown_seconds
        )
        if cooldown_until > now:
            remaining = int((cooldown_until - now).total_seconds()) + 1
            raise RecoveryCodeCooldownError(remaining)

    def for_login(self, login: str) -> tuple[User, str]:
        user = self._repo.get_by_login(login)
        if user is None:
            raise TelegramLoginUnavailableError()
        if not user.is_active:
            raise TelegramLoginUnavailableError()
        if not user.telegram_chat_id:
            raise TelegramLoginUnavailableError()
        return user, self(user.id)

    def for_user_id(self, admin_id: int) -> tuple[User, str]:
        user = self._repo.get_by_id(admin_id)
        if user is None:
            raise AdminNotFoundError(admin_id)
        if not user.is_active:
            raise AdminInactiveError()
        if not user.telegram_chat_id:
            raise TelegramLoginUnavailableError()
        return user, self(user.id)
