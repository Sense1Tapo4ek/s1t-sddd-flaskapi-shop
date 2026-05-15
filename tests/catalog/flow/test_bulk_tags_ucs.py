"""Flow tests for tag-bulk use cases.

Mocks ITaxonomyRepo. Verifies:
- Each per-id call reaches the repo.
- DomainError from the repo becomes a BulkFailure row with the correct reason code.
- Filter mode iterates pages via cursor until exhausted.
"""
from __future__ import annotations

from unittest.mock import create_autospec

import pytest

from catalog.app.interfaces import ITaxonomyRepo
from catalog.app.use_cases import (
    BulkDeleteTagsCommand,
    BulkDeleteTagsUseCase,
    BulkSetTagsActiveCommand,
    BulkSetTagsActiveUseCase,
)
from catalog.domain import TagInUseError, TagNotFoundError
from shared.ports.driving.bulk_schemas import BulkTargetFilter, BulkTargetIds

pytestmark = pytest.mark.flow


def _ids(*xs: int) -> BulkTargetIds:
    return BulkTargetIds(ids=list(xs))


# ─── BulkSetTagsActiveUseCase ────────────────────────────────────────


class TestBulkSetTagsActive:
    def test_ids_mode_happy_path(self):
        """
        Given 3 tag ids,
        When the UC runs in ids-mode with active=True,
        Then repo.set_tag_active is called once per id and ok=3.
        """
        repo = create_autospec(ITaxonomyRepo, instance=True)
        uc = BulkSetTagsActiveUseCase(_repo=repo)

        result = uc(BulkSetTagsActiveCommand(target=_ids(1, 2, 3), active=True))

        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []
        assert repo.set_tag_active.call_count == 3
        repo.set_tag_active.assert_any_call(1, True)

    def test_partial_failure_when_one_id_missing(self):
        """
        Given 3 ids and one missing in the repo,
        When the UC runs,
        Then failed contains exactly that id with reason "TAG_NOT_FOUND".
        """
        repo = create_autospec(ITaxonomyRepo, instance=True)

        def side_effect(tag_id: int, _active: bool) -> None:
            if tag_id == 2:
                raise TagNotFoundError(2)

        repo.set_tag_active.side_effect = side_effect
        uc = BulkSetTagsActiveUseCase(_repo=repo)

        result = uc(BulkSetTagsActiveCommand(target=_ids(1, 2, 3), active=False))

        assert result.total == 3
        assert result.ok == 2
        assert [f.id for f in result.failed] == [2]
        assert result.failed[0].reason == "TAG_NOT_FOUND"

    def test_filter_mode_iterates_via_cursor(self):
        """
        Given a filter target,
        When iter_tag_ids_by_filter returns two pages,
        Then both pages are processed and total reflects all ids.
        """
        repo = create_autospec(ITaxonomyRepo, instance=True)
        repo.iter_tag_ids_by_filter.side_effect = [
            ([10, 11], "11"),
            ([12], None),
        ]
        uc = BulkSetTagsActiveUseCase(_repo=repo)

        result = uc(
            BulkSetTagsActiveCommand(
                target=BulkTargetFilter(filter={"q": "x"}),
                active=False,
            )
        )

        assert result.total == 3
        assert result.ok == 3
        assert repo.set_tag_active.call_count == 3


# ─── BulkDeleteTagsUseCase ───────────────────────────────────────────


class TestBulkDeleteTags:
    def test_happy_path(self):
        """
        Given 3 tag ids,
        When the UC runs,
        Then repo.bulk_delete_tag_one is called 3 times and ok=3.
        """
        repo = create_autospec(ITaxonomyRepo, instance=True)
        uc = BulkDeleteTagsUseCase(_repo=repo)

        result = uc(BulkDeleteTagsCommand(target=_ids(1, 2, 3)))

        assert result.ok == 3
        assert result.failed == []
        assert repo.bulk_delete_tag_one.call_count == 3

    def test_partial_failure_when_tag_in_use(self):
        """
        Given a tag that raises TagInUseError,
        When the UC runs,
        Then that id appears in failed[] with reason "tag_in_use".
        """
        repo = create_autospec(ITaxonomyRepo, instance=True)

        def side_effect(tag_id: int) -> None:
            if tag_id == 7:
                raise TagInUseError(7)

        repo.bulk_delete_tag_one.side_effect = side_effect
        uc = BulkDeleteTagsUseCase(_repo=repo)

        result = uc(BulkDeleteTagsCommand(target=_ids(5, 7, 9)))

        assert result.ok == 2
        assert [f.id for f in result.failed] == [7]
        assert result.failed[0].reason == "tag_in_use"

    def test_partial_failure_when_tag_not_found(self):
        """
        Given a tag that raises TagNotFoundError,
        When the UC runs,
        Then that id appears in failed[] with reason "TAG_NOT_FOUND".
        """
        repo = create_autospec(ITaxonomyRepo, instance=True)

        def side_effect(tag_id: int) -> None:
            if tag_id == 7:
                raise TagNotFoundError(7)

        repo.bulk_delete_tag_one.side_effect = side_effect
        uc = BulkDeleteTagsUseCase(_repo=repo)

        result = uc(BulkDeleteTagsCommand(target=_ids(5, 7, 9)))

        assert result.ok == 2
        assert [f.id for f in result.failed] == [7]
        assert result.failed[0].reason == "TAG_NOT_FOUND"
