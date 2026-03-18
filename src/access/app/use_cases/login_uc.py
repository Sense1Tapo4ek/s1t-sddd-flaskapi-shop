from dataclasses import dataclass

from shared.helpers.security import create_jwt, verify_password

from ...domain import InvalidPasswordError
from ..commands import LoginCommand
from ..interfaces import IAdminRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginUseCase:
    _repo: IAdminRepo
    _jwt_secret: str

    def __call__(self, cmd: LoginCommand) -> str:
        user = self._repo.get_by_login(cmd.login)
        if user is None or not verify_password(cmd.password, user.password_hash):
            raise InvalidPasswordError()

        # Issue JWT
        return create_jwt(
            payload={"sub": user.id, "login": user.login}, secret=self._jwt_secret
        )
