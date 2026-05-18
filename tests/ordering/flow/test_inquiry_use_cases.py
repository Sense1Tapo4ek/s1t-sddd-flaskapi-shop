import copy

import pytest

from ordering.app import (
    ArchiveInquiryCommand,
    ArchiveInquiryUseCase,
    InquiryNotFoundError,
    CreateInquiryCommand,
    CreateInquiryUseCase,
    ChangeInquiryStatusCommand,
    ChangeInquiryStatusUseCase,
)
from ordering.domain import InvalidInquiryTransitionError, Inquiry, InquiryStatus


pytestmark = pytest.mark.flow


class InMemoryInquiryRepo:
    def __init__(self, *, inquiries: list[Inquiry] | None = None, next_id: int = 1) -> None:
        self.inquiries = {i.id: copy.deepcopy(i) for i in inquiries or []}
        self._next_id = next_id
        self.saved: list[Inquiry] = []
        self.events: list[tuple[str, int]] = []

    def next_id(self) -> int:
        inquiry_id = self._next_id
        self._next_id += 1
        return inquiry_id

    def save(self, inquiry: Inquiry) -> None:
        self.events.append(("save", inquiry.id))
        snapshot = copy.deepcopy(inquiry)
        self.saved.append(snapshot)
        self.inquiries[inquiry.id] = snapshot

    def get_by_id(self, inquiry_id: int) -> Inquiry | None:
        self.events.append(("get_by_id", inquiry_id))
        return self.inquiries.get(inquiry_id)


class RecordingNotificationAcl:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.inquiries: list[Inquiry] = []

    def notify_inquiry_created(self, inquiry: Inquiry) -> None:
        self.inquiries.append(inquiry)
        if self.fail:
            raise RuntimeError("telegram is unavailable")


def _inquiry(*, inquiry_id: int = 1, status: InquiryStatus = InquiryStatus.NEW) -> Inquiry:
    inquiry = Inquiry.create(
        id=inquiry_id,
        name="Alice",
        message="Call back please",
        phone="+375291234567",
    )
    inquiry.status = status
    return inquiry


class TestCreateInquiryUseCase:
    def test_saves_created_inquiry_and_notifies(self):
        """
        Given valid inquiry input and working notification ACL,
        When creating the inquiry,
        Then the use case saves the new inquiry and notifies about it.
        """
        repo = InMemoryInquiryRepo(next_id=42)
        notification_acl = RecordingNotificationAcl()
        use_case = CreateInquiryUseCase(_repo=repo, _notification_acl=notification_acl)

        inquiry_id = use_case(
            CreateInquiryCommand(
                name="Alice",
                message="Leave near the door",
                phone="+375291234567",
            )
        )

        assert inquiry_id == 42
        assert len(repo.saved) == 1
        saved = repo.saved[0]
        assert saved.id == 42
        assert saved.name == "Alice"
        assert saved.phone == "+375291234567"
        assert saved.message == "Leave near the door"
        assert saved.status is InquiryStatus.NEW
        assert notification_acl.inquiries[0].id == saved.id

    def test_notification_failure_does_not_break_creation(self):
        """
        Given valid inquiry input and a failing notification ACL,
        When creating the inquiry,
        Then the inquiry is still saved and its id is returned.
        """
        repo = InMemoryInquiryRepo(next_id=7)
        notification_acl = RecordingNotificationAcl(fail=True)
        use_case = CreateInquiryUseCase(_repo=repo, _notification_acl=notification_acl)

        inquiry_id = use_case(
            CreateInquiryCommand(name="Bob", message="I have a question")
        )

        assert inquiry_id == 7
        assert len(repo.saved) == 1
        assert repo.saved[0].id == 7


class TestChangeInquiryStatusUseCase:
    def test_saves_valid_status_transition(self):
        """
        Given an existing inquiry in NEW status,
        When changing to IN_PROGRESS,
        Then the use case saves the updated inquiry.
        """
        inquiry = _inquiry(inquiry_id=5, status=InquiryStatus.NEW)
        repo = InMemoryInquiryRepo(inquiries=[inquiry])
        use_case = ChangeInquiryStatusUseCase(_repo=repo)

        result = use_case(
            ChangeInquiryStatusCommand(inquiry_id=5, new_status=InquiryStatus.IN_PROGRESS.value)
        )

        assert result == 5
        assert inquiry.status is InquiryStatus.NEW  # original unchanged
        assert len(repo.saved) == 1
        assert repo.saved[0].status is InquiryStatus.IN_PROGRESS
        assert repo.events == [("get_by_id", 5), ("save", 5)]

    def test_missing_inquiry_raises_not_found(self):
        """
        Given no inquiry with the requested id,
        When changing status,
        Then the use case raises InquiryNotFoundError.
        """
        repo = InMemoryInquiryRepo()
        use_case = ChangeInquiryStatusUseCase(_repo=repo)

        with pytest.raises(InquiryNotFoundError) as exc_info:
            use_case(ChangeInquiryStatusCommand(inquiry_id=404, new_status="in_progress"))

        assert exc_info.value.code == "INQUIRY_NOT_FOUND"
        assert repo.saved == []

    def test_illegal_transition_propagates_and_does_not_save(self):
        """
        Given an inquiry in IN_PROGRESS and trying to go back to NEW,
        When changing status,
        Then IllegalInquiryTransitionError propagates and nothing is saved.
        """
        from ordering.domain import IllegalInquiryTransitionError

        inquiry = _inquiry(inquiry_id=9, status=InquiryStatus.IN_PROGRESS)
        repo = InMemoryInquiryRepo(inquiries=[inquiry])
        use_case = ChangeInquiryStatusUseCase(_repo=repo)

        with pytest.raises(IllegalInquiryTransitionError) as exc_info:
            use_case(ChangeInquiryStatusCommand(inquiry_id=9, new_status=InquiryStatus.NEW.value))

        assert exc_info.value.code == "illegal_transition"
        assert inquiry.status is InquiryStatus.IN_PROGRESS
        assert repo.saved == []

    def test_unknown_status_string_raises_transition_error(self):
        """
        Given an existing inquiry and an unknown status string,
        When changing status,
        Then the use case raises a domain transition error and does not save.
        """
        inquiry = _inquiry(inquiry_id=13, status=InquiryStatus.NEW)
        repo = InMemoryInquiryRepo(inquiries=[inquiry])
        use_case = ChangeInquiryStatusUseCase(_repo=repo)

        with pytest.raises(InvalidInquiryTransitionError) as exc_info:
            use_case(ChangeInquiryStatusCommand(inquiry_id=13, new_status="shipped"))

        assert exc_info.value.code == "INVALID_TRANSITION"
        assert repo.saved == []
