"""Bulk activate/deactivate products. Per-row mutation through the runner,
domain errors become BulkFailure rows."""
from __future__ import annotations

from dataclasses import dataclass

from shared.app.bulk_runner import BulkRunner
from shared.ports.driving.bulk_schemas import BulkResultSchema, BulkTarget

from ..interfaces import IProductRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkSetProductsActiveCommand:
    target: BulkTarget
    active: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkSetProductsActiveUseCase:
    _repo: IProductRepo

    def __call__(self, cmd: BulkSetProductsActiveCommand) -> BulkResultSchema:
        def process_one(product_id: int) -> None:
            self._repo.set_active(int(product_id), cmd.active)

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_ids_by_filter,
        )
        return runner.run(cmd.target)
