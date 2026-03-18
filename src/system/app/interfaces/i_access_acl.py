from typing import Protocol, runtime_checkable


@runtime_checkable
class IAccessAcl(Protocol):
    """
    Anti-Corruption Layer interface to communicate with the Access Context.
    """

    def reset_admin_password(self) -> str: ...
    def generate_recovery_code(self) -> str: ...
