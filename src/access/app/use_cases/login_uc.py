from dataclasses import dataclass
from datetime import datetime, timezone

from shared.domain import AccountType
from shared.helpers.security import create_jwt, verify_password

from access.config import AccessConfig
from access.permissions import resolve_permissions
from ...domain import (
    AdminInactiveError,
    CustomerInactiveError,
    InvalidPasswordError,
    User,
)
from ...domain.customer_agg import Customer
from ..commands import LoginCommand
from ..interfaces import IAdminRepo, ICustomerRepo

def create_access_token(
    user: User | Customer,
    config: AccessConfig,
    *,
    account_type: AccountType,
    token_version: int,
    remember_me: bool = False,
    csrf_token: str | None = None,
) -> str:
    if account_type is AccountType.ADMIN:
        expires_hours = 24 * 30 if remember_me else 24
        payload: dict = {
            "sub": user.id,
            "login": user.login,
            "role": user.role,
            "permissions": resolve_permissions(user.role, config),
            "account_type": AccountType.ADMIN.value,
            "tv": token_version,
        }
    else:
        expires_hours = config.customer_jwt_remember_me_ttl_hours if remember_me else config.customer_jwt_ttl_hours
        payload = {
            "sub": user.id,
            "email": user.email,
            "account_type": AccountType.CUSTOMER.value,
            "tv": token_version,
        }

    if csrf_token:
        payload["csrf"] = csrf_token

    return create_jwt(
        payload=payload,
        secret=config.jwt_secret,
        expires_hours=expires_hours,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginUseCase:
    _admin_repo: IAdminRepo
    _customer_repo: ICustomerRepo
    _config: AccessConfig

    def __call__(self, cmd: LoginCommand) -> str:
        if "@" in cmd.login:
            return self._authenticate_customer(cmd)
        return self._authenticate_admin(cmd)

    def _authenticate_admin(self, cmd: LoginCommand) -> str:
        user = self._admin_repo.get_by_login(cmd.login)
        if user is None or not verify_password(cmd.password, user.password_hash):
            raise InvalidPasswordError()
        if not user.is_active:
            raise AdminInactiveError()

        self._admin_repo.update_last_login(user.id, datetime.now(timezone.utc))

        return create_access_token(
            user,
            self._config,
            account_type=AccountType.ADMIN,
            token_version=user.token_version,
            remember_me=cmd.remember_me,
            csrf_token=cmd.csrf_token,
        )

    def _authenticate_customer(self, cmd: LoginCommand) -> str:
        customer = self._customer_repo.get_by_email(cmd.login)
        if customer is None or not verify_password(cmd.password, customer.password_hash):
            raise InvalidPasswordError()
        if not customer.is_active:
            raise CustomerInactiveError()

        self._customer_repo.update_last_login(customer.id, datetime.now(timezone.utc))

        return create_access_token(
            customer,
            self._config,
            account_type=AccountType.CUSTOMER,
            token_version=customer.token_version,
            remember_me=cmd.remember_me,
            csrf_token=cmd.csrf_token,
        )
