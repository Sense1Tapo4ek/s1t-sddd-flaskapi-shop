from dataclasses import dataclass
from typing import TypeVar, Generic, Callable, Any, ClassVar
from sqlalchemy import Date, DateTime, asc, cast, desc, func, select
from sqlalchemy.orm import Session

from shared.generics.pagination import PaginatedResult, PaginationParams

TDomain = TypeVar("TDomain")
TModel = TypeVar("TModel")


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlBaseRepo(Generic[TDomain, TModel]):
    """
    Base generic SQL repository providing common data access patterns.
    Handles dynamic filtering, sorting, and pagination.
    """

    _session_factory: Callable[[], Session]

    def _to_domain(self, model: TModel) -> TDomain:
        """
        Maps an SQLAlchemy model to a Domain Aggregate.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _to_domain")

    def _apply_filters(self, stmt: Any, filters: dict[str, Any]) -> Any:
        """
        Applies dynamic WHERE clauses to the statement based on filter suffixes.
        Intelligently handles DateTime columns by casting them to Date for accurate daily filtering.
        """
        for key, value in filters.items():
            if value == "" or value is None:
                continue

            field_name, op = key.split("__", 1) if "__" in key else (key, "eq")
            column = getattr(self._model_class, field_name, None)

            if column is None:
                continue

            # Check if the column is a date/time type
            is_date = isinstance(column.type, (DateTime, Date))
            target_col = func.date(column) if is_date else column

            if op == "eq":
                stmt = stmt.where(target_col == value)
            elif op == "ilike":
                # Only apply ILIKE to string/text columns
                stmt = stmt.where(func.lower(column).contains(func.lower(str(value))))
            elif op == "gte":
                stmt = stmt.where(target_col >= value)
            elif op == "lte":
                stmt = stmt.where(target_col <= value)

        return stmt

    def _paginate(
        self,
        session: Session,
        stmt: Any,
        params: PaginationParams,
        default_sort: str = "id",
        load_options: list[Any] | None = None,
    ) -> PaginatedResult[TDomain]:
        """
        Executes a paginated database query with optional eager loading.
        Returns a domain-mapped PaginatedResult.
        """
        stmt = self._apply_filters(stmt, params.filters)
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        sort_field = params.sort_by or default_sort
        sort_column = getattr(self._model_class, sort_field, None)

        if sort_column is not None:
            stmt = stmt.order_by(
                desc(sort_column) if params.sort_dir == "desc" else asc(sort_column)
            )

        if load_options:
            stmt = stmt.options(*load_options)

        rows = (
            session.execute(stmt.offset(params.offset).limit(params.limit))
            .scalars()
            .unique()
            .all()
        )

        return PaginatedResult(
            items=[self._to_domain(r) for r in rows],
            total=total,
            page=params.page,
            limit=params.limit,
        )
