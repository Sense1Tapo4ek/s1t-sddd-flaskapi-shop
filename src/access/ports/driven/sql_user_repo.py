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
            recovery_code_hash=model.recovery_code_hash,
            recovery_code_expires=model.recovery_code_expires,
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
    def update_password(self, user_id: int, password_hash: str) -> User | None:
        with self._session_factory() as session:
            model = session.get(UserModel, user_id)
            if not model:
                return None
            model.password_hash = password_hash
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
                session.commit()

    @handle_db_errors("clear recovery code")
    def clear_recovery_code(self, user_id: int) -> None:
        with self._session_factory() as session:
            model = session.get(UserModel, user_id)
            if model:
                model.recovery_code_hash = None
                model.recovery_code_expires = None
                session.commit()
