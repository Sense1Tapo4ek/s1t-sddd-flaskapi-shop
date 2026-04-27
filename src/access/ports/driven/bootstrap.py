from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from access.adapters.driven.db.models import UserModel
from access.config import AccessConfig
from root.config import RootConfig
from shared.helpers.security import hash_password, verify_password

logger = logging.getLogger("access.bootstrap")


def bootstrap_access_defaults(
    session_factory: Callable[[], Session],
    *,
    access_config: AccessConfig,
    root_config: RootConfig,
) -> None:
    with session_factory() as session:
        _ensure_user(
            session,
            login=access_config.default_login,
            password=access_config.default_password,
            role="owner",
            telegram_chat_id=access_config.default_telegram_chat_id,
            password_changed_at=None,
        )

        superadmin_password = access_config.superadmin_password
        if not superadmin_password and root_config.app_env == "dev":
            superadmin_password = "superadmin"
        if superadmin_password:
            superadmin = _ensure_user(
                session,
                login=access_config.superadmin_login,
                password=superadmin_password,
                role="superadmin",
                telegram_chat_id=access_config.superadmin_telegram_chat_id,
                password_changed_at=(
                    None
                    if superadmin_password == "superadmin"
                    else datetime.now(timezone.utc)
                ),
            )
            _mark_legacy_superadmin_password_if_changed(superadmin)
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


def _mark_legacy_superadmin_password_if_changed(user: UserModel) -> None:
    if user.password_changed_at is not None:
        return
    if not verify_password("superadmin", user.password_hash):
        user.password_changed_at = datetime.now(timezone.utc)
