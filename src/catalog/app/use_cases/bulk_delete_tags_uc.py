"""Bulk-delete tags. Each row deleted in its own transaction;
TagInUseError / TagNotFoundError surface as partial-failure rows, not 5xx."""
from __future__ import annotations

from dataclasses import dataclass

from shared.app.bulk_runner import BulkRunner
from shared.ports.driving.bulk_schemas import BulkResultSchema, BulkTarget

from ..interfaces import ITaxonomyRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkDeleteTagsCommand:
    target: BulkTarget


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkDeleteTagsUseCase:
    _repo: ITaxonomyRepo

    def __call__(self, cmd: BulkDeleteTagsCommand) -> BulkResultSchema:
        def process_one(tag_id: int) -> None:
            self._repo.bulk_delete_tag_one(int(tag_id))

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_tag_ids_by_filter,
        )
        return runner.run(cmd.target)
