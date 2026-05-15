"""Bulk-delete products. Each row deleted in its own transaction;
ProductInUseByActiveOrderError surfaces as a partial-failure row, not 5xx."""
from __future__ import annotations

from dataclasses import dataclass

from shared.app.bulk_runner import BulkRunner
from shared.ports.driving.bulk_schemas import BulkResultSchema, BulkTarget

from ..interfaces import IProductRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkDeleteProductsCommand:
    target: BulkTarget


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkDeleteProductsUseCase:
    _repo: IProductRepo

    def __call__(self, cmd: BulkDeleteProductsCommand) -> BulkResultSchema:
        def process_one(product_id: int) -> None:
            self._repo.bulk_delete_one(int(product_id))

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_ids_by_filter,
        )
        return runner.run(cmd.target)
