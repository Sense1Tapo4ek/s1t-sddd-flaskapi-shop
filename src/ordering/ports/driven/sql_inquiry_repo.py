from dataclasses import dataclass
from typing import ClassVar
from sqlalchemy import asc, select

from shared.generics.pagination import PaginatedResult, PaginationParams
from shared.adapters.driven.db.repository import SqlBaseRepo
from shared.helpers.db import handle_db_errors

from ordering.app.interfaces import IInquiryRepo
from ordering.domain import Inquiry, InquiryStatus
from ordering.adapters.driven import InquiryModel


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlInquiryRepo(SqlBaseRepo[Inquiry, InquiryModel], IInquiryRepo):

    _model_class: ClassVar[type[InquiryModel]] = InquiryModel

    def _to_domain(self, model: InquiryModel) -> Inquiry:
        return Inquiry(
            id=model.id,
            name=model.name,
            phone=model.phone,
            contact_email=model.contact_email,
            message=model.message,
            status=InquiryStatus(model.status),
            created_at=model.created_at,
            author_user_id=model.author_user_id,
        )

    def next_id(self) -> int:
        return 0

    @handle_db_errors("get inquiry")
    def get_by_id(self, inquiry_id: int) -> Inquiry | None:
        with self._session_factory() as session:
            model = session.get(InquiryModel, inquiry_id)
            return self._to_domain(model) if model else None

    @handle_db_errors("save inquiry")
    def save(self, inquiry: Inquiry) -> None:
        with self._session_factory() as session:
            if inquiry.id == 0:
                model = InquiryModel(
                    name=inquiry.name,
                    phone=inquiry.phone,
                    contact_email=inquiry.contact_email,
                    message=inquiry.message,
                    status=inquiry.status.value,
                    created_at=inquiry.created_at,
                    author_user_id=inquiry.author_user_id,
                )
                session.add(model)
                session.flush()
                inquiry.id = model.id
            else:
                model = session.get(InquiryModel, inquiry.id)
                if model:
                    model.status = inquiry.status.value
            session.commit()

    @handle_db_errors("list inquiries")
    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Inquiry]:
        with self._session_factory() as session:
            stmt = select(InquiryModel)
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
        ``inquiries.id`` ascending so that ``cursor`` is the last id from
        the previous page."""
        with self._session_factory() as session:
            stmt = select(InquiryModel.id)
            stmt = self._apply_filters(stmt, filter_payload or {})

            if cursor is not None:
                try:
                    cursor_id = int(cursor)
                except (TypeError, ValueError):
                    cursor_id = 0
                stmt = stmt.where(InquiryModel.id > cursor_id)

            stmt = stmt.order_by(asc(InquiryModel.id)).limit(limit)
            rows = session.execute(stmt).scalars().all()
            ids = list(rows)
            next_cursor = str(ids[-1]) if len(ids) == limit else None
            return ids, next_cursor
