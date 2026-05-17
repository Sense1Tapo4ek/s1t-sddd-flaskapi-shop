from dataclasses import dataclass

from access.app import LoginUseCase

from .schemas import LoginIn, LoginOut


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessFacade:
    _login_uc: LoginUseCase

    def login(self, schema: LoginIn, *, csrf_token: str | None = None) -> LoginOut:
        token = self._login_uc(schema.to_command(csrf_token=csrf_token))
        return LoginOut(token=token)
