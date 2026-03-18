from dataclasses import dataclass
from typing import ClassVar
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.generics.errors import DrivenPortError
from shared.generics.pagination import PaginatedResult, PaginationParams
from shared.adapters.driven.db.repository import SqlBaseRepo

from ordering.app.interfaces import IOrderRepo
from ordering.domain import Order, OrderStatus
from ordering.adapters.driven import OrderModel


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlOrderRepo(SqlBaseRepo[Order, OrderModel], IOrderRepo):
    """
    SQLAlchemy implementation of the Order Repository.
    Handles data persistence and retrieval for the Ordering context.
    """

    _model_class: ClassVar[type[OrderModel]] = OrderModel

    def _to_domain(self, model: OrderModel) -> Order:
        """Converts an SQLAlchemy OrderModel to a Domain Order aggregate."""
        return Order(
            id=model.id,
            name=model.name,
            phone=model.phone,
            comment=model.comment,
            status=OrderStatus(model.status),
            created_at=model.created_at,
        )

    def next_id(self) -> int:
        """
        Generates the next unique identity for an Order.
        Returns 0 to delegate ID generation to the DB auto-increment.
        """
        return 0

    def get_by_id(self, order_id: int) -> Order | None:
        """Retrieves an order by its unique identifier."""
        try:
            with self._session_factory() as session:
                model = session.get(OrderModel, order_id)
                return self._to_domain(model) if model else None
        except Exception as e:
            raise DrivenPortError(f"DB Error get order: {e}")

    def save(self, order: Order) -> None:
        """Persists a new order or updates an existing one based on its identity."""
        try:
            with self._session_factory() as session:
                if order.id == 0:
                    model = OrderModel(
                        name=order.name,
                        phone=order.phone,
                        comment=order.comment,
                        status=order.status.value,
                        created_at=order.created_at,
                    )
                    session.add(model)
                    session.flush()
                    order.id = model.id
                else:
                    model = session.get(OrderModel, order.id)
                    if model:
                        model.status = order.status.value
                session.commit()
        except Exception as e:
            raise DrivenPortError(f"DB Error save order: {e}")

    def delete(self, order_id: int) -> None:
        """Deletes an order by its ID."""
        try:
            with self._session_factory() as session:
                model = session.get(OrderModel, order_id)
                if model:
                    session.delete(model)
                    session.commit()
        except Exception as e:
            raise DrivenPortError(f"DB Error delete order: {e}")

    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Order]:
        """
        Retrieves a paginated list of orders.
        Delegates dynamic filtering and sorting to the base repository.
        """
        try:
            with self._session_factory() as session:
                stmt = select(OrderModel)
                return self._paginate(
                    session=session, stmt=stmt, params=params, default_sort="created_at"
                )
        except Exception as e:
            raise DrivenPortError(f"DB Error list orders: {e}")
