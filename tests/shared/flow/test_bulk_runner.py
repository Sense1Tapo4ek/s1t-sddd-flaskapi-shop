from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from shared.generics.errors import DomainError
from shared.app.bulk_runner import BulkRunner
from shared.ports.driving.bulk_schemas import (
    BulkTargetFilter,
    BulkTargetIds,
)

pytestmark = pytest.mark.flow


class _DomainNotFound(DomainError):
    pass


def _ok(_id: UUID) -> None:
    return None


def _always_fail(reason: str):
    def _processor(_id: UUID) -> None:
        raise _DomainNotFound("oops", code=reason)
    return _processor


def _fail_on(target_ids: set[UUID], reason: str):
    def _processor(aid: UUID) -> None:
        if aid in target_ids:
            raise _DomainNotFound("nope", code=reason)
    return _processor


class TestBulkRunnerIdsMode:
    def test_all_success(self):
        """
        Given 3 ids and a processor that always succeeds,
        When run() is called,
        Then total=ok=3 and no failures.
        """
        ids = [uuid4() for _ in range(3)]
        runner = BulkRunner(process_one=_ok)

        result = runner.run(BulkTargetIds(ids=ids))

        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []

    def test_partial_failure_reports_failed_ids(self):
        """
        Given 3 ids where one raises DomainError,
        When run() is called,
        Then ok=2, failed has the single failing id with its code.
        """
        ids = [uuid4() for _ in range(3)]
        bad = {ids[1]}
        runner = BulkRunner(process_one=_fail_on(bad, "tag_in_use"))

        result = runner.run(BulkTargetIds(ids=ids))

        assert result.total == 3
        assert result.ok == 2
        assert len(result.failed) == 1
        assert result.failed[0].id == ids[1]
        assert result.failed[0].reason == "tag_in_use"

    def test_all_fail_returns_zero_ok(self):
        ids = [uuid4() for _ in range(2)]
        runner = BulkRunner(process_one=_always_fail("locked"))

        result = runner.run(BulkTargetIds(ids=ids))

        assert result.total == 2
        assert result.ok == 0
        assert {f.reason for f in result.failed} == {"locked"}


class TestBulkRunnerFilterMode:
    def test_paginates_through_batches(self):
        """
        Given a loader that returns 3 pages of 2 ids,
        When run() is called with batch_size=2,
        Then total=6, ok=6, loader was called 3 times.
        """
        pages = [
            [uuid4(), uuid4()],
            [uuid4(), uuid4()],
            [uuid4(), uuid4()],
        ]
        call_log: list[tuple[str | None, int]] = []

        def loader(_filter, *, cursor, limit):
            call_log.append((cursor, limit))
            if cursor is None:
                return pages[0], "c1"
            if cursor == "c1":
                return pages[1], "c2"
            return pages[2], None

        runner = BulkRunner(process_one=_ok, load_filter_page=loader, batch_size=2)

        result = runner.run(BulkTargetFilter(filter={"active": True}))

        assert result.total == 6
        assert result.ok == 6
        assert result.failed == []
        assert len(call_log) == 3

    def test_empty_filter_returns_zero(self):
        def loader(_filter, *, cursor, limit):
            return [], None

        runner = BulkRunner(process_one=_ok, load_filter_page=loader)

        result = runner.run(BulkTargetFilter(filter={}))

        assert result.total == 0
        assert result.ok == 0

    def test_filter_mode_without_loader_raises(self):
        runner = BulkRunner(process_one=_ok)
        with pytest.raises(RuntimeError, match="load_filter_page"):
            runner.run(BulkTargetFilter(filter={}))

    def test_partial_failure_inside_batches(self):
        """
        Given 2 batches of 2 ids where one id in batch 2 fails,
        When run() is called,
        Then total=4, ok=3, failed=[that one id].
        """
        page1 = [uuid4(), uuid4()]
        page2 = [uuid4(), uuid4()]
        bad = {page2[0]}

        def loader(_filter, *, cursor, limit):
            if cursor is None:
                return page1, "c1"
            return page2, None

        runner = BulkRunner(
            process_one=_fail_on(bad, "stale"),
            load_filter_page=loader,
            batch_size=2,
        )

        result = runner.run(BulkTargetFilter(filter={}))

        assert result.total == 4
        assert result.ok == 3
        assert result.failed[0].id == page2[0]
        assert result.failed[0].reason == "stale"
