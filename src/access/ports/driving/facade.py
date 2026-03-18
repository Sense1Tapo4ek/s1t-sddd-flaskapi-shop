from dataclasses import dataclass

from access.app import (
    ChangePasswordUseCase,
    LoginUseCase,
    ChangePasswordCommand,
    ResetPasswordUseCase,
    GenerateRecoveryCodeUseCase,
    VerifyRecoveryCodeUseCase,
)

from .schemas import LoginIn, LoginOut


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessFacade:
    _login_uc: LoginUseCase
    _change_password_uc: ChangePasswordUseCase
    _reset_password_uc: ResetPasswordUseCase
    _generate_code_uc: GenerateRecoveryCodeUseCase
    _verify_code_uc: VerifyRecoveryCodeUseCase

    def login(self, schema: LoginIn) -> LoginOut:
        token = self._login_uc(schema.to_command())
        return LoginOut(token=token)

    def change_password(self, admin_id: int, schema: dict) -> None:
        cmd = ChangePasswordCommand(
            admin_id=admin_id,
            new_password=schema["new_password"],
            old_password=schema.get("old_password"),
        )
        self._change_password_uc(cmd)

    def reset_password(self, admin_id: int = 1) -> str:
        """Called by System Context via ACL to reset and fetch new password."""
        return self._reset_password_uc(admin_id=admin_id)

    def generate_recovery_code(self, admin_id: int = 1) -> str:
        """Generate one-time login code. Called by System Context via ACL."""
        return self._generate_code_uc(admin_id=admin_id)

    def verify_recovery_code(self, code: str, admin_id: int = 1) -> str:
        """Verify code and return JWT token."""
        return self._verify_code_uc(code=code, admin_id=admin_id)
