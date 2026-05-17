from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from access.adapters.driven.db.models import CustomerModel
from access.app.interfaces.i_customer_repo import ICustomerRepo
from access.domain import Customer
from access.domain.errors import CustomerNotFoundError, EmailAlreadyRegisteredError
from shared.helpers.db import handle_db_errors


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlCustomerRepo(ICustomerRepo):
    _session_factory: Callable[[], Session]

    def _to_domain(self, model: CustomerModel) -> Customer:
        return Customer(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            is_active=model.is_active,
            created_at=model.created_at,
            token_version=model.token_version or 0,
            last_login_at=model.last_login_at,
            recovery_code_hash=model.recovery_code_hash,
            recovery_code_expires=model.recovery_code_expires,
            recovery_code_attempts=model.recovery_code_attempts or 0,
            recovery_code_last_sent_at=model.recovery_code_last_sent_at,
            recovery_code_locked_until=model.recovery_code_locked_until,
        )

    @handle_db_errors("get customer by email")
    def get_by_email(self, email: str) -> Customer | None:
        with self._session_factory() as session:
            model = session.execute(
                select(CustomerModel).where(CustomerModel.email == email)
            ).scalar_one_or_none()
            return self._to_domain(model) if model else None

    @handle_db_errors("get customer by id")
    def get_by_id(self, customer_id: int) -> Customer | None:
        with self._session_factory() as session:
            model = session.get(CustomerModel, customer_id)
            return self._to_domain(model) if model else None

    @handle_db_errors("create customer")
    def create(self, *, email: str, password_hash: str) -> Customer:
        with self._session_factory() as session:
            model = CustomerModel(email=email, password_hash=password_hash)
            session.add(model)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise EmailAlreadyRegisteredError(email)
            session.refresh(model)
            return self._to_domain(model)

    @handle_db_errors("update customer password")
    def update_password(self, customer_id: int, password_hash: str) -> None:
        with self._session_factory() as session:
            model = session.get(CustomerModel, customer_id)
            if model:
                model.password_hash = password_hash
                session.commit()

    @handle_db_errors("set customer recovery code")
    def set_recovery_code(self, customer_id: int, code_hash: str, expires: datetime) -> None:
        with self._session_factory() as session:
            model = session.get(CustomerModel, customer_id)
            if model:
                model.recovery_code_hash = code_hash
                model.recovery_code_expires = expires
                model.recovery_code_attempts = 0
                model.recovery_code_last_sent_at = datetime.now(expires.tzinfo)
                model.recovery_code_locked_until = None
                session.commit()

    @handle_db_errors("clear customer recovery code")
    def clear_recovery_code(self, customer_id: int) -> None:
        with self._session_factory() as session:
            model = session.get(CustomerModel, customer_id)
            if model:
                model.recovery_code_hash = None
                model.recovery_code_expires = None
                model.recovery_code_attempts = 0
                model.recovery_code_locked_until = None
                session.commit()

    @handle_db_errors("record customer recovery failure")
    def record_recovery_failure(
        self,
        customer_id: int,
        attempts: int,
        locked_until: datetime | None,
    ) -> None:
        with self._session_factory() as session:
            model = session.get(CustomerModel, customer_id)
            if model:
                model.recovery_code_attempts = attempts
                model.recovery_code_locked_until = locked_until
                session.commit()

    @handle_db_errors("get customer token version")
    def get_token_version(self, customer_id: int) -> int | None:
        with self._session_factory() as session:
            model = session.get(CustomerModel, customer_id)
            if model is None:
                return None
            return model.token_version

    @handle_db_errors("bump customer token version")
    def bump_token_version(self, customer_id: int) -> int:
        with self._session_factory() as session:
            result = session.execute(
                update(CustomerModel)
                .where(CustomerModel.id == customer_id)
                .values(token_version=CustomerModel.token_version + 1)
            )
            if result.rowcount == 0:
                raise CustomerNotFoundError(customer_id)
            session.commit()
            model = session.get(CustomerModel, customer_id)
            return model.token_version

    @handle_db_errors("update customer last login")
    def update_last_login(self, customer_id: int, when: datetime) -> None:
        with self._session_factory() as session:
            model = session.get(CustomerModel, customer_id)
            if model:
                model.last_login_at = when
                session.commit()
