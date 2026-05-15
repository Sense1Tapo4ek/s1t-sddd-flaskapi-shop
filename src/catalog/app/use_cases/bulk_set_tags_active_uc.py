"""Bulk activate/deactivate tags. Per-row mutation through the runner,
TagNotFoundError surfaces as a partial-failure row, not 5xx."""
from __future__ import annotations

from dataclasses import dataclass

from shared.app.bulk_runner import BulkRunner
from shared.ports.driving.bulk_schemas import BulkResultSchema, BulkTarget

from ..interfaces import ITaxonomyRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkSetTagsActiveCommand:
    target: BulkTarget
    active: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkSetTagsActiveUseCase:
    _repo: ITaxonomyRepo

    def __call__(self, cmd: BulkSetTagsActiveCommand) -> BulkResultSchema:
        def process_one(tag_id: int) -> None:
            self._repo.set_tag_active(int(tag_id), cmd.active)

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_tag_ids_by_filter,
        )
        return runner.run(cmd.target)
