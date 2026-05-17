import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from access.config import AccessConfig
from shared.helpers.security import generate_recovery_code, hash_password, verify_password
from ...domain.errors import EmailRecoveryFailedError
from ..commands import SendCustomerRecoveryCommand
from ..interfaces import ICustomerRepo, IEmailSender
from ..services.recovery_logic import should_send

_DUMMY_PASSWORD_HASH = hash_password("dummy-anti-timing-value")


def _burn_constant_time() -> None:
    verify_password("dummy", _DUMMY_PASSWORD_HASH)
    time.sleep(secrets.randbelow(20) / 1000.0)


@dataclass(frozen=True, slots=True, kw_only=True)
class SendCustomerRecoveryCodeUseCase:
    _repo: ICustomerRepo
    _email_sender: IEmailSender
    _config: AccessConfig

    def __call__(self, cmd: SendCustomerRecoveryCommand) -> None:
        now = datetime.now(timezone.utc)
        customer = self._repo.get_by_email(cmd.email)

        if customer is None:
            _burn_constant_time()
            return

        can_send, _ = should_send(
            customer,
            now=now,
            cooldown_seconds=self._config.customer_recovery_code_cooldown_seconds,
        )
        if not can_send:
            _burn_constant_time()
            return

        code = generate_recovery_code()
        code_hash = hash_password(code)
        expires = now + timedelta(minutes=self._config.customer_recovery_code_ttl_minutes)
        self._repo.set_recovery_code(customer.id, code_hash, expires)

        try:
            subject = "Восстановление пароля"
            body = (
                f"Ваш код: {code}\n"
                f"Код действителен {self._config.customer_recovery_code_ttl_minutes} минут."
            )
            self._email_sender.send(customer.email, subject, body)
        except Exception as exc:
            self._repo.clear_recovery_code(customer.id)
            raise EmailRecoveryFailedError() from exc
