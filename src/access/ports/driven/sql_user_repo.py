from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session

from access.adapters.driven import UserModel
from access.app.interfaces import IAdminRepo
from access.domain import User
from shared.helpers.db import handle_db_errors


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlUserRepo(IAdminRepo):
    _session_factory: Callable[[], Session]

    def _to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id, login=model.login, password_hash=model.password_hash,
            role=model.role,
            telegram_chat_id=model.telegram_chat_id,
            is_active=model.is_active,
            password_changed_at=model.password_changed_at,
            recovery_code_hash=model.recovery_code_hash,
            recovery_code_expires=model.recovery_code_expires,
            recovery_code_attempts=model.recovery_code_attempts or 0,
            recovery_code_last_sent_at=model.recovery_code_last_sent_at,
            recovery_code_locked_until=model.recovery_code_locked_until,
        )

    @handle_db_errors("get user by login")
    def get_by_login(self, login: str) -> User | None:
        with self._session_factory() as session:
            model = session.execute(
                select(UserModel).where(UserModel.login == login)
            ).scalar_one_or_none()
            return self._to_domain(model) if model else None

    @handle_db_errors("get user by id")
    def get_by_id(self, user_id: int) -> User | None:
        with self._session_factory() as session:
            model = session.get(UserModel, user_id)
            return self._to_domain(model) if model else None

    @handle_db_errors("update password")
    def update_password(
        self,
        user_id: int,
        password_hash: str,
        password_changed_at: datetime | None = None,
    ) -> User | None:
        with self._session_factory() as session:
            model = session.get(UserModel, user_id)
            if not model:
                return None
            model.password_hash = password_hash
            model.password_changed_at = password_changed_at
            session.commit()
            session.refresh(model)
            return self._to_domain(model)

    @handle_db_errors("list order notification recipients")
    def list_order_notification_recipients(self) -> list[User]:
        with self._session_factory() as session:
            models = session.execute(
                select(UserModel)
                .where(UserModel.is_active.is_(True))
                .where(UserModel.role.in_(("owner", "superadmin")))
                .where(UserModel.telegram_chat_id.is_not(None))
                .order_by(UserModel.id.asc())
            ).scalars().all()
            return [self._to_domain(model) for model in models if model.telegram_chat_id]

    @handle_db_errors("update telegram chat id")
    def update_telegram_chat_id(self, user_id: int, chat_id: str | None) -> User | None:
        with self._session_factory() as session:
            model = session.get(UserModel, user_id)
            if not model:
                return None
            model.telegram_chat_id = chat_id or None
            session.commit()
            session.refresh(model)
            return self._to_domain(model)

    @handle_db_errors("set recovery code")
    def set_recovery_code(self, user_id: int, code_hash: str, expires: datetime) -> None:
        with self._session_factory() as session:
            model = session.get(UserModel, user_id)
            if model:
                model.recovery_code_hash = code_hash
                model.recovery_code_expires = expires
                model.recovery_code_attempts = 0
                model.recovery_code_last_sent_at = datetime.now(expires.tzinfo)
                model.recovery_code_locked_until = None
                session.commit()

    @handle_db_errors("record recovery failure")
    def record_recovery_failure(
        self,
        user_id: int,
        attempts: int,
        locked_until: datetime | None,
    ) -> None:
        with self._session_factory() as session:
            model = session.get(UserModel, user_id)
            if model:
                model.recovery_code_attempts = attempts
                model.recovery_code_locked_until = locked_until
                session.commit()

    @handle_db_errors("clear recovery code")
    def clear_recovery_code(self, user_id: int) -> None:
        with self._session_factory() as session:
            model = session.get(UserModel, user_id)
            if model:
                model.recovery_code_hash = None
                model.recovery_code_expires = None
                model.recovery_code_attempts = 0
                model.recovery_code_locked_until = None
                session.commit()
