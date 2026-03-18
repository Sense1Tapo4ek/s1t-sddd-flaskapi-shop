import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from shared.helpers.security import hash_password
from ...domain.errors import AdminNotFoundError
from ..interfaces import IAdminRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ResetPasswordUseCase:
    """
    System-level password reset (triggered via ACL).
    Generates a secure temporary password.
    """

    _repo: IAdminRepo

    def __call__(self, admin_id: int = 1) -> str:
        user = self._repo.get_by_id(admin_id)
        if user is None:
            raise AdminNotFoundError(admin_id)

        new_password = secrets.token_urlsafe(8)
        new_hash = hash_password(new_password)
        self._repo.update_password(user.id, new_hash)

        return new_password


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateRecoveryCodeUseCase:
    """
    Generates a 6-digit one-time login code, stores its hash with 5-min expiry.
    Returns the plain code (to be sent via Telegram).
    """

    _repo: IAdminRepo

    def __call__(self, admin_id: int = 1) -> str:
        user = self._repo.get_by_id(admin_id)
        if user is None:
            raise AdminNotFoundError(admin_id)

        code = f"{secrets.randbelow(1000000):06d}"
        code_hash = hash_password(code)
        expires = datetime.now(timezone.utc) + timedelta(minutes=5)

        self._repo.set_recovery_code(user.id, code_hash, expires)
        return code
