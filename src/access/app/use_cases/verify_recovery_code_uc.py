from dataclasses import dataclass
from datetime import datetime, timezone

from access.config import AccessConfig
from shared.domain import AccountType
from shared.helpers.security import verify_password
from ...domain import AdminInactiveError, RecoveryCodeLockedError, User
from ...domain.errors import InvalidRecoveryCodeError  # noqa: F401 — re-exported for backward compat
from ..interfaces import IAdminRepo
from ..services.recovery_logic import verify_code
from .login_uc import create_access_token


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifyRecoveryCodeUseCase:
    _repo: IAdminRepo
    _config: AccessConfig

    def _verify_code(self, user: User, code: str) -> None:
        if not user.is_active:
            raise AdminInactiveError()

        outcome = verify_code(
            user,
            code,
            now=datetime.now(timezone.utc),
            max_attempts=self._config.recovery_code_max_attempts,
            lockout_minutes=self._config.recovery_code_lockout_minutes,
            verify_password_fn=verify_password,
        )

        if outcome.locked and not outcome.invalid:
            raise RecoveryCodeLockedError()

        if outcome.expired:
            self._repo.clear_recovery_code(user.id)
            raise InvalidRecoveryCodeError()

        if outcome.invalid:
            if outcome.new_attempts > 0:
                self._repo.record_recovery_failure(
                    user.id,
                    outcome.new_attempts,
                    outcome.new_locked_until,
                )
            if outcome.new_locked_until is not None:
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
            account_type=AccountType.ADMIN,
            token_version=user.token_version,
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
