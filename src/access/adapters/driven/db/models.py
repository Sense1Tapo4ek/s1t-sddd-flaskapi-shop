from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, DateTime
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
    role: Mapped[str] = mapped_column(String(30), default="owner", nullable=False)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recovery_code_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recovery_code_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recovery_code_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovery_code_last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recovery_code_locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
