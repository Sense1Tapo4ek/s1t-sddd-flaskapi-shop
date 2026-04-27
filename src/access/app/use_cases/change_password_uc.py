from dataclasses import dataclass
from datetime import datetime, timezone
from shared.helpers.security import verify_password, hash_password
from ...domain.errors import (
    AdminNotFoundError,
    InvalidPasswordError,
    PasswordConfirmationRequiredError,
    WeakPasswordError,
)
from ..interfaces import IAdminRepo
from ..commands import ChangePasswordCommand
from .verify_recovery_code_uc import VerifyRecoveryCodeUseCase


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangePasswordUseCase:
    """
    Allows an authenticated user to change their own password.
    """

    _repo: IAdminRepo
    _verify_code_uc: VerifyRecoveryCodeUseCase

    def __call__(self, cmd: ChangePasswordCommand) -> None:
        if len(cmd.new_password or "") < 5:
            raise WeakPasswordError()

        # 1. Get current state to verify old password
        user = self._repo.get_by_id(cmd.admin_id)
        if user is None:
            raise AdminNotFoundError(cmd.admin_id)

        # 2. Require one explicit factor: current password or one-time Telegram code.
        old_password = (cmd.old_password or "").strip()
        confirmation_code = (cmd.confirmation_code or "").strip()
        confirmed = False
        old_password_failed = False

        if old_password:
            confirmed = verify_password(old_password, user.password_hash)
            old_password_failed = not confirmed

        if not confirmed and confirmation_code:
            self._verify_code_uc.verify_for_user(user.id, confirmation_code)
            confirmed = True

        if not confirmed:
            if old_password_failed:
                raise InvalidPasswordError()
            raise PasswordConfirmationRequiredError()

        # 3. Hash and persist via the specific interface method
        new_hash = hash_password(cmd.new_password)
        self._repo.update_password(user.id, new_hash, datetime.now(timezone.utc))
