from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from shared.adapters.driven import Base


class UserModel(Base):
    """
    Maps to the existing 'admins' table for backward compatibility.
    """

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    recovery_code_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recovery_code_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
