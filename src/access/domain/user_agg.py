from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class User:
    """
    Aggregate Root for a system user (Staff/Admin).
    """

    id: int
    login: str
    password_hash: str
    recovery_code_hash: str | None = field(default=None)
    recovery_code_expires: datetime | None = field(default=None)
