from dataclasses import dataclass
from datetime import datetime, timezone

from access.config import AccessConfig
from shared.domain import AccountType
from shared.helpers.security import hash_password, verify_password
from ...domain.errors import (
    CustomerInactiveError,
    InvalidRecoveryCodeError,
    RecoveryCodeLockedError,
    WeakPasswordError,
)
from ..commands import VerifyCustomerRecoveryCommand
from ..interfaces import ICustomerRepo
from ..services.recovery_logic import verify_code
from ..services.session_cache import SessionCache
from .login_uc import create_access_token


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifyCustomerRecoveryUseCase:
    _repo: ICustomerRepo
    _config: AccessConfig
    _cache: SessionCache

    def __call__(self, cmd: VerifyCustomerRecoveryCommand) -> str:
        if len(cmd.new_password) < 8:
            raise WeakPasswordError(min_length=8)

        customer = self._repo.get_by_email(cmd.email)
        if customer is None:
            raise InvalidRecoveryCodeError()

        if not customer.is_active:
            raise CustomerInactiveError()

        outcome = verify_code(
            customer,
            cmd.code,
            now=datetime.now(timezone.utc),
            max_attempts=self._config.customer_recovery_code_max_attempts,
            lockout_minutes=self._config.customer_recovery_code_lockout_minutes,
            verify_password_fn=verify_password,
        )

        if outcome.locked and not outcome.invalid:
            raise RecoveryCodeLockedError()

        if outcome.expired:
            self._repo.clear_recovery_code(customer.id)
            raise InvalidRecoveryCodeError()

        if outcome.invalid:
            if outcome.new_attempts > 0:
                self._repo.record_recovery_failure(
                    customer.id,
                    outcome.new_attempts,
                    outcome.new_locked_until,
                )
            if outcome.new_locked_until is not None:
                raise RecoveryCodeLockedError()
            raise InvalidRecoveryCodeError()

        new_hash = hash_password(cmd.new_password)
        self._repo.update_password(customer.id, new_hash)
        self._repo.clear_recovery_code(customer.id)
        new_tv = self._repo.bump_token_version(customer.id)
        self._cache.invalidate(AccountType.CUSTOMER.value, customer.id)
        self._repo.update_last_login(customer.id, datetime.now(timezone.utc))

        return create_access_token(
            customer,
            self._config,
            account_type=AccountType.CUSTOMER,
            token_version=new_tv,
            csrf_token=cmd.csrf_token,
        )
