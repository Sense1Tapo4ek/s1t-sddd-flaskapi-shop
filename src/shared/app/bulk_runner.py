"""Generic runner for bulk operations.

Iterates over targeted aggregate ids in batches and applies a
per-aggregate callable. Each ``DomainError`` raised by ``process_one``
becomes a ``BulkFailureSchema`` row; everything else propagates out so
the global error handler maps it to 5xx.

The runner is layer-agnostic — it lives in ``shared/app/`` because
every context's bulk use cases reuse the same pagination + partial-
failure semantics described in
``docs/superpowers/specs/2026-05-15-bulk-actions-design.md`` §5.1.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, Protocol
from uuid import UUID

from shared.generics.errors import DomainError
from shared.ports.driving.bulk_schemas import (
    BulkFailureSchema,
    BulkResultSchema,
    BulkTarget,
    BulkTargetFilter,
    BulkTargetIds,
)

DEFAULT_BATCH_SIZE = 200

logger = logging.getLogger("shared.bulk")


class IFilterIdLoader(Protocol):
    """Loads aggregate ids that match a context-specific filter.

    Implementations live in driven repos. The runner is filter-blind:
    it only needs ``(filter_payload, cursor, limit) -> (ids, next_cursor)``.
    Return ``next_cursor=None`` when the page is the last one.
    """

    def __call__(
        self,
        filter_payload: dict,
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[UUID], str | None]:
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkRunner:
    """Synchronous bulk runner. UCs that are sync-only call ``.run``.

    Async variant lives at :func:`run_bulk_async` for symmetry; current
    project is sync (Flask + SQLAlchemy sync sessions), so the sync
    version is the default.
    """

    process_one: Callable[[UUID], None]
    load_filter_page: IFilterIdLoader | None = None
    batch_size: int = DEFAULT_BATCH_SIZE

    def run(self, target: BulkTarget) -> BulkResultSchema:
        if isinstance(target, BulkTargetIds):
            return self._run_ids(target.ids)
        if isinstance(target, BulkTargetFilter):
            return self._run_filter(target.filter)
        raise TypeError(f"unknown BulkTarget: {type(target).__name__}")

    def _run_ids(self, ids: list[UUID]) -> BulkResultSchema:
        failed: list[BulkFailureSchema] = []
        ok = 0
        for aggregate_id in ids:
            if self._apply(aggregate_id, failed):
                ok += 1
        return BulkResultSchema(total=len(ids), ok=ok, failed=failed)

    def _run_filter(self, filter_payload: dict) -> BulkResultSchema:
        if self.load_filter_page is None:
            raise RuntimeError(
                "BulkRunner.load_filter_page is required for filter-mode targets"
            )

        failed: list[BulkFailureSchema] = []
        ok = 0
        total = 0
        cursor: str | None = None

        while True:
            ids, cursor = self.load_filter_page(
                filter_payload, cursor=cursor, limit=self.batch_size
            )
            if not ids:
                break
            total += len(ids)
            for aggregate_id in ids:
                if self._apply(aggregate_id, failed):
                    ok += 1
            if cursor is None:
                break

        return BulkResultSchema(total=total, ok=ok, failed=failed)

    def _apply(self, aggregate_id: UUID, failed: list[BulkFailureSchema]) -> bool:
        try:
            self.process_one(aggregate_id)
            return True
        except DomainError as e:
            failed.append(BulkFailureSchema(id=aggregate_id, reason=e.code))
            return False


@dataclass(frozen=True, slots=True, kw_only=True)
class AsyncBulkRunner:
    """Async variant of :class:`BulkRunner`. Kept for parity; not used
    by the current Flask stack but available if an async UC needs it."""

    process_one: Callable[[UUID], Awaitable[None]]
    load_filter_page: IFilterIdLoader | None = None
    batch_size: int = DEFAULT_BATCH_SIZE

    async def run(self, target: BulkTarget) -> BulkResultSchema:
        if isinstance(target, BulkTargetIds):
            return await self._run_ids(target.ids)
        if isinstance(target, BulkTargetFilter):
            return await self._run_filter(target.filter)
        raise TypeError(f"unknown BulkTarget: {type(target).__name__}")

    async def _run_ids(self, ids: Iterable[UUID]) -> BulkResultSchema:
        failed: list[BulkFailureSchema] = []
        ok = 0
        total = 0
        for aggregate_id in ids:
            total += 1
            if await self._apply(aggregate_id, failed):
                ok += 1
        return BulkResultSchema(total=total, ok=ok, failed=failed)

    async def _run_filter(self, filter_payload: dict) -> BulkResultSchema:
        if self.load_filter_page is None:
            raise RuntimeError(
                "AsyncBulkRunner.load_filter_page is required for filter-mode targets"
            )

        failed: list[BulkFailureSchema] = []
        ok = 0
        total = 0
        cursor: str | None = None

        while True:
            ids, cursor = self.load_filter_page(
                filter_payload, cursor=cursor, limit=self.batch_size
            )
            if not ids:
                break
            total += len(ids)
            for aggregate_id in ids:
                if await self._apply(aggregate_id, failed):
                    ok += 1
            if cursor is None:
                break

        return BulkResultSchema(total=total, ok=ok, failed=failed)

    async def _apply(self, aggregate_id: UUID, failed: list[BulkFailureSchema]) -> bool:
        try:
            await self.process_one(aggregate_id)
            return True
        except DomainError as e:
            failed.append(BulkFailureSchema(id=aggregate_id, reason=e.code))
            return False
