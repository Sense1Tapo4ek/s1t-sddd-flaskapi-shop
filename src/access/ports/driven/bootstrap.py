from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from access.adapters.driven.db.models import UserModel
from access.config import AccessConfig
from shared.helpers.security import hash_password

logger = logging.getLogger("access.bootstrap")


def bootstrap_access_defaults(
    session_factory: Callable[[], Session],
    *,
    access_config: AccessConfig,
) -> None:
    # "@" в login админа сломает дисптач "/auth/login" — admin будет
    # классифицирован как customer. Падаем рано.
    if "@" in access_config.default_login:
        raise ValueError(
            "ACCESS_DEFAULT_LOGIN must not contain '@' — "
            "'@' is reserved for customer email identifiers."
        )

    role = "superadmin" if access_config.promote_to_superadmin else "owner"
    with session_factory() as session:
        _ensure_user(
            session,
            login=access_config.default_login,
            password=access_config.default_password,
            role=role,
            telegram_chat_id=access_config.default_telegram_chat_id,
            password_changed_at=None,
        )
        session.commit()


def _ensure_user(
    session: Session,
    *,
    login: str,
    password: str,
    role: str,
    telegram_chat_id: str = "",
    password_changed_at: datetime | None = None,
) -> UserModel:
    user = session.execute(
        select(UserModel).where(UserModel.login == login)
    ).scalar_one_or_none()
    if user is None:
        user = UserModel(
            login=login,
            password_hash=hash_password(password),
            role=role,
            telegram_chat_id=telegram_chat_id or None,
            is_active=True,
            password_changed_at=password_changed_at,
        )
        session.add(user)
        session.flush()
        logger.info("Created %s user: %s", role, login)
    else:
        user.role = role
        user.is_active = True
        if telegram_chat_id and not user.telegram_chat_id:
            user.telegram_chat_id = telegram_chat_id
    return user
