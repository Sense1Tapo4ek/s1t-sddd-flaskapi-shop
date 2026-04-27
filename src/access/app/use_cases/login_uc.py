from dataclasses import dataclass

from shared.helpers.security import create_jwt, verify_password

from access.config import AccessConfig
from access.permissions import resolve_permissions
from ...domain import AdminInactiveError, InvalidPasswordError, User
from ..commands import LoginCommand
from ..interfaces import IAdminRepo


def create_access_token(
    user: User,
    config: AccessConfig,
    *,
    remember_me: bool = False,
    csrf_token: str | None = None,
) -> str:
    expires_hours = 24 * 30 if remember_me else 24
    payload = {
        "sub": user.id,
        "login": user.login,
        "role": user.role,
        "permissions": resolve_permissions(user.role, config),
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
    _repo: IAdminRepo
    _config: AccessConfig

    def __call__(self, cmd: LoginCommand) -> str:
        user = self._repo.get_by_login(cmd.login)
        if user is None or not verify_password(cmd.password, user.password_hash):
            raise InvalidPasswordError()
        if not user.is_active:
            raise AdminInactiveError()

        return create_access_token(
            user,
            self._config,
            remember_me=cmd.remember_me,
            csrf_token=cmd.csrf_token,
        )
