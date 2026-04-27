from dataclasses import dataclass

from access.app import (
    ChangePasswordUseCase,
    LoginUseCase,
    ChangePasswordCommand,
    ResetPasswordUseCase,
    GenerateRecoveryCodeUseCase,
    VerifyRecoveryCodeUseCase,
    IAdminRepo,
)
from access.domain import AdminNotFoundError, User

from .schemas import LoginIn, LoginOut


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessFacade:
    _repo: IAdminRepo
    _login_uc: LoginUseCase
    _change_password_uc: ChangePasswordUseCase
    _reset_password_uc: ResetPasswordUseCase
    _generate_code_uc: GenerateRecoveryCodeUseCase
    _verify_code_uc: VerifyRecoveryCodeUseCase

    def login(self, schema: LoginIn, *, csrf_token: str | None = None) -> LoginOut:
        token = self._login_uc(schema.to_command(csrf_token=csrf_token))
        return LoginOut(token=token)

    def change_password(self, admin_id: int, schema: dict) -> None:
        cmd = ChangePasswordCommand(
            admin_id=admin_id,
            new_password=schema["new_password"],
            old_password=schema.get("old_password"),
            confirmation_code=schema.get("confirmation_code"),
        )
        self._change_password_uc(cmd)

    def get_user(self, admin_id: int) -> User:
        user = self._repo.get_by_id(admin_id)
        if user is None:
            raise AdminNotFoundError(admin_id)
        return user

    def reset_password(self, admin_id: int = 1) -> str:
        """Called by System Context via ACL to reset and fetch new password."""
        return self._reset_password_uc(admin_id=admin_id)

    def generate_recovery_code(self, admin_id: int = 1) -> str:
        """Generate one-time login code. Called by System Context via ACL."""
        return self._generate_code_uc(admin_id=admin_id)

    def clear_recovery_code(self, admin_id: int = 1) -> None:
        """Clear one-time login code. Called by System Context via ACL after failed delivery."""
        self._repo.clear_recovery_code(admin_id)

    def verify_recovery_code(
        self,
        code: str,
        admin_id: int = 1,
        *,
        csrf_token: str | None = None,
    ) -> str:
        """Verify code and return JWT token."""
        return self._verify_code_uc(code=code, admin_id=admin_id, csrf_token=csrf_token)

    def request_telegram_login_code(self, login: str) -> tuple[str, str, str]:
        """Return (login, telegram_chat_id, one-time-code) for Telegram login."""
        user, code = self._generate_code_uc.for_login(login=login)
        return user.login, user.telegram_chat_id or "", code

    def request_user_confirmation_code(self, admin_id: int) -> tuple[str, str, str]:
        """Return (login, telegram_chat_id, one-time-code) for authenticated user."""
        user, code = self._generate_code_uc.for_user_id(admin_id=admin_id)
        return user.login, user.telegram_chat_id or "", code

    def verify_telegram_login_code(
        self,
        *,
        login: str,
        code: str,
        remember_me: bool = False,
        csrf_token: str | None = None,
    ) -> LoginOut:
        token = self._verify_code_uc.for_login(
            login=login,
            code=code,
            remember_me=remember_me,
            csrf_token=csrf_token,
        )
        return LoginOut(token=token)

    def update_telegram_chat_id(self, admin_id: int, chat_id: str | None) -> None:
        self._repo.update_telegram_chat_id(admin_id, chat_id)

    def order_notification_recipients(self) -> list[User]:
        return self._repo.list_order_notification_recipients()
