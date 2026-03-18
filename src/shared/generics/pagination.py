from dataclasses import dataclass, field
from typing import Generic, TypeVar, Any

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PaginationParams:
    page: int = 1
    limit: int = 20
    sort_by: str | None = None
    sort_dir: str = "asc"
    # {"status": "new", "min_price": 50})
    filters: dict[str, Any] = field(default_factory=dict)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


@dataclass(frozen=True, slots=True)
class PaginatedResult(Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int

    @property
    def total_pages(self) -> int:
        if self.limit == 0:
            return 0
        return (self.total + self.limit - 1) // self.limit
