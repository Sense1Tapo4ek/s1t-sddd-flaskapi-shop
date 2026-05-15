"""Bulk apply tag changes — replace / add / remove."""
from __future__ import annotations

from dataclasses import dataclass

from shared.app.bulk_runner import BulkRunner
from shared.ports.driving.bulk_schemas import BulkResultSchema, BulkTarget

from ...domain import InvalidBulkTagModeError, TagNotFoundError
from ..interfaces import BulkTagMode, IProductRepo, ITaxonomyRepo

ALLOWED_MODES: frozenset[str] = frozenset({"replace", "add", "remove"})


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkAssignProductsTagsCommand:
    target: BulkTarget
    tag_ids: list[int]
    mode: BulkTagMode  # "replace" | "add" | "remove"


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkAssignProductsTagsUseCase:
    _repo: IProductRepo
    _taxonomy_repo: ITaxonomyRepo

    def __call__(self, cmd: BulkAssignProductsTagsCommand) -> BulkResultSchema:
        if cmd.mode not in ALLOWED_MODES:
            raise InvalidBulkTagModeError(cmd.mode)

        for tag_id in cmd.tag_ids:
            if self._taxonomy_repo.get_tag(tag_id) is None:
                raise TagNotFoundError(tag_id)

        def process_one(product_id: int) -> None:
            self._repo.apply_tags(int(product_id), cmd.tag_ids, cmd.mode)

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_ids_by_filter,
        )
        return runner.run(cmd.target)
