from dataclasses import dataclass

from access.config import AccessConfig
from shared.domain import AccountType
from shared.helpers.security import hash_password
from ...domain.errors import WeakPasswordError
from ..commands import RegisterCustomerCommand
from ..interfaces import ICustomerRepo
from .login_uc import create_access_token


@dataclass(frozen=True, slots=True, kw_only=True)
class RegisterCustomerUseCase:
    _repo: ICustomerRepo
    _config: AccessConfig

    def __call__(self, cmd: RegisterCustomerCommand) -> str:
        if len(cmd.password) < 8:
            raise WeakPasswordError(min_length=8)

        customer = self._repo.create(
            email=cmd.email,
            password_hash=hash_password(cmd.password),
        )

        return create_access_token(
            customer,
            self._config,
            account_type=AccountType.CUSTOMER,
            token_version=customer.token_version,
            csrf_token=cmd.csrf_token,
        )
