"""Flow tests for ArchiveInquiryUseCase.

Verifies:
- Archive from NEW succeeds.
- Archive from CLOSED succeeds.
- Archive from IN_PROGRESS succeeds.
- Archive from ARCHIVED raises InquiryAlreadyTerminalError.
- Missing inquiry raises InquiryNotFoundError.
"""
import copy

import pytest

from ordering.app import ArchiveInquiryCommand, ArchiveInquiryUseCase, InquiryNotFoundError
from ordering.domain import Inquiry, InquiryStatus

pytestmark = pytest.mark.flow


class InMemoryInquiryRepo:
    def __init__(self, *, inquiries: list[Inquiry] | None = None) -> None:
        self.inquiries = {i.id: copy.deepcopy(i) for i in inquiries or []}
        self.saved: list[Inquiry] = []
        self.events: list[tuple[str, int]] = []

    def next_id(self) -> int:
        return 0

    def save(self, inquiry: Inquiry) -> None:
        self.events.append(("save", inquiry.id))
        snapshot = copy.deepcopy(inquiry)
        self.saved.append(snapshot)
        self.inquiries[inquiry.id] = snapshot

    def get_by_id(self, inquiry_id: int) -> Inquiry | None:
        self.events.append(("get_by_id", inquiry_id))
        return self.inquiries.get(inquiry_id)


def _inquiry(inquiry_id: int, status: InquiryStatus) -> Inquiry:
    inq = Inquiry.create(id=inquiry_id, name="Alice", message="Hello")
    inq.status = status
    return inq


class TestArchiveInquiryUseCase:
    @pytest.mark.parametrize(
        "initial_status",
        [InquiryStatus.NEW, InquiryStatus.IN_PROGRESS, InquiryStatus.CLOSED],
    )
    def test_archive_from_active_status_succeeds(self, initial_status):
        """
        Given an inquiry in an active status (NEW, IN_PROGRESS, or CLOSED),
        When ArchiveInquiryUseCase runs,
        Then the inquiry transitions to ARCHIVED and is saved.
        """
        inquiry = _inquiry(1, initial_status)
        repo = InMemoryInquiryRepo(inquiries=[inquiry])
        use_case = ArchiveInquiryUseCase(_repo=repo)

        result = use_case(ArchiveInquiryCommand(inquiry_id=1))

        assert result == 1
        assert len(repo.saved) == 1
        assert repo.saved[0].status is InquiryStatus.ARCHIVED

    def test_archive_from_archived_raises_terminal_error(self):
        """
        Given an inquiry already in ARCHIVED status,
        When ArchiveInquiryUseCase runs,
        Then InquiryAlreadyTerminalError is raised and nothing is saved.
        """
        from ordering.domain import InquiryAlreadyTerminalError

        inquiry = _inquiry(2, InquiryStatus.ARCHIVED)
        repo = InMemoryInquiryRepo(inquiries=[inquiry])
        use_case = ArchiveInquiryUseCase(_repo=repo)

        with pytest.raises(InquiryAlreadyTerminalError) as exc_info:
            use_case(ArchiveInquiryCommand(inquiry_id=2))

        assert exc_info.value.code == "inquiry_already_terminal"
        assert repo.saved == []

    def test_missing_inquiry_raises_not_found(self):
        """
        Given no inquiry with the requested id,
        When ArchiveInquiryUseCase runs,
        Then InquiryNotFoundError is raised.
        """
        repo = InMemoryInquiryRepo()
        use_case = ArchiveInquiryUseCase(_repo=repo)

        with pytest.raises(InquiryNotFoundError) as exc_info:
            use_case(ArchiveInquiryCommand(inquiry_id=999))

        assert exc_info.value.code == "INQUIRY_NOT_FOUND"
        assert repo.saved == []
