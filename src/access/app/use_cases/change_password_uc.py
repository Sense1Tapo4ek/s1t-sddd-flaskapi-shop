from dataclasses import dataclass
from shared.helpers.security import verify_password, hash_password
from ...domain.errors import AdminNotFoundError, InvalidPasswordError
from ..interfaces import IAdminRepo
from ..commands import ChangePasswordCommand


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangePasswordUseCase:
    """
    Allows an authenticated user to change their own password.
    """

    _repo: IAdminRepo

    def __call__(self, cmd: ChangePasswordCommand) -> None:
        # 1. Get current state to verify old password
        user = self._repo.get_by_id(cmd.admin_id)
        if user is None:
            raise AdminNotFoundError(cmd.admin_id)

        # 2. Check credentials (skip if old_password not provided — trusted session)
        if cmd.old_password is not None:
            if not verify_password(cmd.old_password, user.password_hash):
                raise InvalidPasswordError()

        # 3. Hash and persist via the specific interface method
        new_hash = hash_password(cmd.new_password)
        self._repo.update_password(user.id, new_hash)
