"""Bulk-assign a category to a set of products.

Target category is validated ONCE before the run — if it doesn't exist
or is not a leaf, every per-row call would fail with the same reason,
so we short-circuit with a setup-level domain error instead.
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.app.bulk_runner import BulkRunner
from shared.ports.driving.bulk_schemas import BulkResultSchema, BulkTarget

from ...domain import CategoryNotFoundError, InvalidProductError
from ..interfaces import IProductRepo, ITaxonomyRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkAssignProductsCategoryCommand:
    target: BulkTarget
    category_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkAssignProductsCategoryUseCase:
    _repo: IProductRepo
    _taxonomy_repo: ITaxonomyRepo

    def __call__(self, cmd: BulkAssignProductsCategoryCommand) -> BulkResultSchema:
        if self._taxonomy_repo.get_category(cmd.category_id) is None:
            raise CategoryNotFoundError(cmd.category_id)
        if not self._taxonomy_repo.is_leaf_category(cmd.category_id):
            raise InvalidProductError(
                "товар можно привязать только к конечной категории"
            )

        def process_one(product_id: int) -> None:
            self._repo.assign_category(int(product_id), cmd.category_id)

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_ids_by_filter,
        )
        return runner.run(cmd.target)
