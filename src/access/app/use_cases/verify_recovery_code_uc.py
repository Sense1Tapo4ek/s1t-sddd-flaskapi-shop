from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from access.config import AccessConfig
from shared.helpers.security import verify_password
from shared.generics.errors import DomainError
from ...domain import AdminInactiveError, RecoveryCodeLockedError, User
from ..interfaces import IAdminRepo
from .login_uc import create_access_token


class InvalidRecoveryCodeError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Неверный или просроченный код",
            code="INVALID_RECOVERY_CODE",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifyRecoveryCodeUseCase:
    """
    Verifies one-time recovery code and issues JWT for login.
    """

    _repo: IAdminRepo
    _config: AccessConfig

    def _as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _verify_code(self, user: User, code: str) -> None:
        if not user.is_active:
            raise AdminInactiveError()

        now = datetime.now(timezone.utc)
        locked_until = self._as_utc(user.recovery_code_locked_until)
        if locked_until and locked_until > now:
            raise RecoveryCodeLockedError()

        if user.recovery_code_hash is None:
            raise InvalidRecoveryCodeError()

        expires = self._as_utc(user.recovery_code_expires)
        if expires is None or expires < now:
            self._repo.clear_recovery_code(user.id)
            raise InvalidRecoveryCodeError()

        if not verify_password(code, user.recovery_code_hash):
            attempts = (user.recovery_code_attempts or 0) + 1
            next_locked_until = None
            if attempts >= self._config.recovery_code_max_attempts:
                next_locked_until = now + timedelta(
                    minutes=self._config.recovery_code_lockout_minutes
                )
            self._repo.record_recovery_failure(
                user.id,
                attempts,
                next_locked_until,
            )
            if next_locked_until is not None:
                raise RecoveryCodeLockedError()
            raise InvalidRecoveryCodeError()

        self._repo.clear_recovery_code(user.id)

    def __call__(
        self,
        code: str,
        admin_id: int = 1,
        *,
        remember_me: bool = False,
        csrf_token: str | None = None,
    ) -> str:
        user = self._repo.get_by_id(admin_id)
        if user is None:
            raise InvalidRecoveryCodeError()

        self._verify_code(user, code)

        return create_access_token(
            user,
            self._config,
            remember_me=remember_me,
            csrf_token=csrf_token,
        )

    def for_login(
        self,
        login: str,
        code: str,
        *,
        remember_me: bool = False,
        csrf_token: str | None = None,
    ) -> str:
        user = self._repo.get_by_login(login)
        if user is None:
            raise InvalidRecoveryCodeError()
        return self(
            code,
            user.id,
            remember_me=remember_me,
            csrf_token=csrf_token,
        )

    def verify_for_user(self, admin_id: int, code: str) -> None:
        user = self._repo.get_by_id(admin_id)
        if user is None:
            raise InvalidRecoveryCodeError()
        self._verify_code(user, code)
