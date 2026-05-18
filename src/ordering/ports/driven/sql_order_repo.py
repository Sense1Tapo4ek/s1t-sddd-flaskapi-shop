from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import asc, select

from shared.generics.pagination import PaginatedResult, PaginationParams
from shared.adapters.driven.db.repository import SqlBaseRepo
from shared.helpers.db import handle_db_errors

from ordering.app.interfaces import IOrderRepo
from ordering.domain import (
    DeliveryInfo,
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
)
from ordering.adapters.driven import OrderModel, OrderItemModel


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlOrderRepo(SqlBaseRepo[Order, OrderModel], IOrderRepo):

    _model_class: ClassVar[type[OrderModel]] = OrderModel

    def _to_domain(self, model: OrderModel) -> Order:
        items = [
            OrderItem(
                product_id=item.product_id,
                title_snapshot=item.title_snapshot,
                unit_price=Decimal(str(item.unit_price)),
                quantity=item.quantity,
            )
            for item in model.items
        ]
        delivery = DeliveryInfo(
            method=DeliveryMethod(model.delivery_method),
            address=model.delivery_address,
            comment=model.delivery_comment,
        )
        return Order(
            id=model.id,
            customer_user_id=model.customer_user_id,
            items=items,
            total=Decimal(str(model.total)),
            delivery=delivery,
            comment=model.comment,
            status=OrderStatus(model.status),
            created_at=model.created_at,
        )

    def next_id(self) -> int:
        return 0  # AUTO_INCREMENT — sentinel; actual id filled on INSERT

    @handle_db_errors("get order")
    def get_by_id(self, order_id: int) -> Order | None:
        with self._session_factory() as session:
            model = session.get(OrderModel, order_id)
            return self._to_domain(model) if model else None

    @handle_db_errors("save order")
    def save(self, order: Order) -> None:
        with self._session_factory() as session:
            if order.id == 0:
                model = OrderModel(
                    customer_user_id=order.customer_user_id,
                    total=order.total,
                    delivery_method=order.delivery.method.value,
                    delivery_address=order.delivery.address,
                    delivery_comment=order.delivery.comment,
                    comment=order.comment,
                    status=order.status.value,
                    created_at=order.created_at,
                )
                for item in order.items:
                    model.items.append(
                        OrderItemModel(
                            product_id=item.product_id,
                            title_snapshot=item.title_snapshot,
                            unit_price=item.unit_price,
                            quantity=item.quantity,
                        )
                    )
                session.add(model)
                session.flush()
                # Post-INSERT id backfill: MySQL AUTO_INCREMENT assigns the pk
                # after flush. Aggregates start with id=0 (sentinel from next_id()),
                # so this one-time mutation is intentional and mirrors SqlInquiryRepo.
                order.id = model.id
            else:
                model = session.get(OrderModel, order.id)
                if model:
                    model.status = order.status.value
            session.commit()

    @handle_db_errors("list orders")
    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Order]:
        with self._session_factory() as session:
            stmt = select(OrderModel)
            return self._paginate(
                session=session, stmt=stmt, params=params, default_sort="created_at"
            )

    # ─── Bulk operations ────────────────────────────────────────────

    def iter_ids_by_filter(
        self,
        filter_payload: dict,
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[int], str | None]:
        """Cursor-paginated id loader for bulk operations. Orders by
        ``orders.id`` ascending so that ``cursor`` is the last id from
        the previous page."""
        with self._session_factory() as session:
            stmt = select(OrderModel.id)
            stmt = self._apply_filters(stmt, filter_payload or {})

            if cursor is not None:
                try:
                    cursor_id = int(cursor)
                except (TypeError, ValueError):
                    cursor_id = 0
                stmt = stmt.where(OrderModel.id > cursor_id)

            stmt = stmt.order_by(asc(OrderModel.id)).limit(limit)
            rows = session.execute(stmt).scalars().all()
            ids = list(rows)
            next_cursor = str(ids[-1]) if len(ids) == limit else None
            return ids, next_cursor
