from dataclasses import dataclass

from system.app.interfaces import IAccessAcl
from access.ports.driving.facade import AccessFacade


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessAcl(IAccessAcl):
    """
    Implements the ACL using the Access Context's public facade.
    """

    _facade: AccessFacade

    def reset_admin_password(self) -> str:
        return self._facade.reset_password()

    def generate_recovery_code(self) -> str:
        return self._facade.generate_recovery_code()
