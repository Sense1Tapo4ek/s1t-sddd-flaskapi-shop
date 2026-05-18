"""Flow tests for BulkChangeInquiryStatusUseCase.

Mocks IInquiryRepo. Verifies:
- Each per-id call loads the inquiry, changes status, and saves.
- Missing inquiry becomes BulkFailure with reason "INQUIRY_NOT_FOUND".
- IllegalInquiryTransitionError becomes BulkFailure with reason "illegal_transition".
- InquiryAlreadyTerminalError becomes BulkFailure with reason "inquiry_already_terminal".
- Unknown status string (ValueError path) becomes BulkFailure with reason "INVALID_TRANSITION".
- Filter mode iterates pages via cursor until exhausted.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import create_autospec, call

import pytest

from ordering.app.interfaces import IInquiryRepo
from ordering.app.use_cases import (
    BulkChangeInquiryStatusCommand,
    BulkChangeInquiryStatusUseCase,
)
from ordering.app.errors import InquiryNotFoundError
from ordering.domain import (
    IllegalInquiryTransitionError,
    InvalidInquiryTransitionError,
    Inquiry,
    InquiryAlreadyTerminalError,
    InquiryStatus,
)
from shared.ports.driving.bulk_schemas import BulkTargetFilter, BulkTargetIds

pytestmark = pytest.mark.flow


def _ids(*xs: int) -> BulkTargetIds:
    return BulkTargetIds(ids=list(xs))


def _inquiry(inquiry_id: int, status: InquiryStatus = InquiryStatus.NEW) -> Inquiry:
    return Inquiry(
        id=inquiry_id,
        name="x",
        phone=None,
        contact_email=None,
        message="test",
        status=status,
        created_at=datetime.now(),
        author_user_id=None,
    )


class TestBulkChangeInquiryStatus:
    def test_ids_mode_happy_path_new_to_in_progress(self):
        """
        Given 3 inquiries all in NEW status,
        When BulkChangeInquiryStatusUseCase runs with target status "in_progress",
        Then get_by_id is called 3 times, save is called 3 times, and ok=3.
        """
        repo = create_autospec(IInquiryRepo, instance=True)
        repo.get_by_id.side_effect = [
            _inquiry(1, InquiryStatus.NEW),
            _inquiry(2, InquiryStatus.NEW),
            _inquiry(3, InquiryStatus.NEW),
        ]
        uc = BulkChangeInquiryStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeInquiryStatusCommand(
                target=_ids(1, 2, 3),
                status="in_progress",
            )
        )

        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []
        assert repo.get_by_id.call_count == 3
        assert repo.save.call_count == 3

    def test_partial_failure_when_inquiry_missing(self):
        """
        Given 3 ids where the middle one does not exist in the repo,
        When the UC runs,
        Then failed contains exactly that id with reason "INQUIRY_NOT_FOUND".
        """
        repo = create_autospec(IInquiryRepo, instance=True)
        repo.get_by_id.side_effect = [
            _inquiry(1, InquiryStatus.NEW),
            None,
            _inquiry(3, InquiryStatus.NEW),
        ]
        uc = BulkChangeInquiryStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeInquiryStatusCommand(
                target=_ids(1, 2, 3),
                status="in_progress",
            )
        )

        assert result.total == 3
        assert result.ok == 2
        assert [f.id for f in result.failed] == [2]
        assert result.failed[0].reason == "INQUIRY_NOT_FOUND"

    def test_partial_failure_when_target_status_illegal(self):
        """
        Given an inquiry in IN_PROGRESS and target status NEW,
        When the UC runs,
        Then the inquiry fails with reason "illegal_transition".
        """
        repo = create_autospec(IInquiryRepo, instance=True)
        repo.get_by_id.side_effect = [_inquiry(7, InquiryStatus.IN_PROGRESS)]
        uc = BulkChangeInquiryStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeInquiryStatusCommand(
                target=_ids(7),
                status="new",
            )
        )

        assert result.total == 1
        assert result.ok == 0
        assert [f.id for f in result.failed] == [7]
        assert result.failed[0].reason == "illegal_transition"
        repo.save.assert_not_called()

    def test_partial_failure_when_current_is_terminal(self):
        """
        Given an inquiry already in ARCHIVED status,
        When the UC runs with target status "in_progress",
        Then the inquiry fails with reason "inquiry_already_terminal".
        """
        repo = create_autospec(IInquiryRepo, instance=True)
        repo.get_by_id.side_effect = [_inquiry(10, InquiryStatus.ARCHIVED)]
        uc = BulkChangeInquiryStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeInquiryStatusCommand(
                target=_ids(10),
                status="in_progress",
            )
        )

        assert result.total == 1
        assert result.ok == 0
        assert [f.id for f in result.failed] == [10]
        assert result.failed[0].reason == "inquiry_already_terminal"
        repo.save.assert_not_called()

    def test_partial_failure_when_target_status_unknown(self):
        """
        Given inquiries in NEW status and a completely unknown target status string,
        When the UC runs,
        Then all inquiries fail with reason "INVALID_TRANSITION".
        """
        repo = create_autospec(IInquiryRepo, instance=True)
        repo.get_by_id.side_effect = [
            _inquiry(1, InquiryStatus.NEW),
            _inquiry(2, InquiryStatus.NEW),
        ]
        uc = BulkChangeInquiryStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeInquiryStatusCommand(
                target=_ids(1, 2),
                status="bogus",
            )
        )

        assert result.total == 2
        assert result.ok == 0
        assert len(result.failed) == 2
        assert result.failed[0].reason == "INVALID_TRANSITION"
        assert result.failed[1].reason == "INVALID_TRANSITION"
        repo.save.assert_not_called()

    def test_filter_mode_iterates_via_cursor(self):
        """
        Given a filter target and iter_ids_by_filter returning two pages,
        When the UC runs with status "in_progress",
        Then all 3 ids from both pages are processed and ok=3.
        """
        repo = create_autospec(IInquiryRepo, instance=True)
        repo.iter_ids_by_filter.side_effect = [
            ([1, 2], "2"),
            ([3], None),
        ]
        repo.get_by_id.side_effect = [
            _inquiry(1, InquiryStatus.NEW),
            _inquiry(2, InquiryStatus.NEW),
            _inquiry(3, InquiryStatus.NEW),
        ]
        uc = BulkChangeInquiryStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeInquiryStatusCommand(
                target=BulkTargetFilter(filter={"status__eq": "new"}),
                status="in_progress",
            )
        )

        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []
        assert repo.save.call_count == 3
