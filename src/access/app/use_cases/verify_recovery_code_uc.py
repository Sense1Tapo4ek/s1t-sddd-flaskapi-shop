from dataclasses import dataclass
from datetime import datetime, timezone

from shared.helpers.security import verify_password, create_jwt
from shared.generics.errors import DomainError
from ..interfaces import IAdminRepo


class InvalidRecoveryCodeError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Неверный или просроченный код",
            code="INVALID_RECOVERY_CODE",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifyRecoveryCodeUseCase:
    """
    Verifies one-time recovery code and issues JWT for login.
    """

    _repo: IAdminRepo
    _jwt_secret: str

    def __call__(self, code: str, admin_id: int = 1) -> str:
        user = self._repo.get_by_id(admin_id)
        if user is None or user.recovery_code_hash is None:
            raise InvalidRecoveryCodeError()

        if user.recovery_code_expires is None or user.recovery_code_expires.replace(
            tzinfo=timezone.utc
        ) < datetime.now(timezone.utc):
            self._repo.clear_recovery_code(user.id)
            raise InvalidRecoveryCodeError()

        if not verify_password(code, user.recovery_code_hash):
            raise InvalidRecoveryCodeError()

        # Code is valid — clear it (one-time use)
        self._repo.clear_recovery_code(user.id)

        return create_jwt(
            payload={"sub": user.id, "login": user.login},
            secret=self._jwt_secret,
        )
