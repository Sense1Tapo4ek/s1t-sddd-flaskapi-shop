from datetime import datetime

import pytest

from ordering.domain import (
    InvalidInquiryTransitionError,
    Inquiry,
    InquiryCreationError,
    InquiryStatus,
)


@pytest.mark.unit
class TestInquiryCreation:
    def test_inquiry_requires_name(self):
        """
        Given inquiry data with an empty name,
        When creating an inquiry,
        Then the domain rejects it.
        """
        with pytest.raises(InquiryCreationError) as exc_info:
            Inquiry.create(id=1, name="", message="Hello")

        assert exc_info.value.code == "INQUIRY_CREATION_FAILED"

    def test_inquiry_requires_message(self):
        """
        Given inquiry data with an empty message,
        When creating an inquiry,
        Then the domain rejects it.
        """
        with pytest.raises(InquiryCreationError) as exc_info:
            Inquiry.create(id=1, name="Alice", message="")

        assert exc_info.value.code == "INQUIRY_CREATION_FAILED"

    def test_inquiry_starts_in_new_status(self):
        """
        Given valid inquiry data,
        When creating an inquiry,
        Then the inquiry starts as NEW with a creation timestamp.
        """
        before_create = datetime.now()

        inquiry = Inquiry.create(id=1, name="Alice", message="Hello there", phone="+375291234567")

        assert inquiry.status is InquiryStatus.NEW
        assert inquiry.created_at >= before_create

    def test_inquiry_optional_fields_default_to_none(self):
        """
        Given inquiry with only required fields,
        When creating,
        Then optional fields are None.
        """
        inquiry = Inquiry.create(id=1, name="Bob", message="Question here")

        assert inquiry.phone is None
        assert inquiry.contact_email is None
        assert inquiry.author_user_id is None


@pytest.mark.unit
class TestInquiryStatusTransitions:
    @pytest.mark.parametrize(
        ("initial_status", "target_status"),
        [
            (InquiryStatus.NEW, InquiryStatus.IN_PROGRESS),
            (InquiryStatus.NEW, InquiryStatus.CLOSED),
            (InquiryStatus.NEW, InquiryStatus.ARCHIVED),
            (InquiryStatus.IN_PROGRESS, InquiryStatus.CLOSED),
            (InquiryStatus.IN_PROGRESS, InquiryStatus.ARCHIVED),
            (InquiryStatus.CLOSED, InquiryStatus.ARCHIVED),
        ],
    )
    def test_allowed_transition_changes_status(self, initial_status, target_status):
        """
        Given an inquiry in a status with an allowed outgoing transition,
        When changing to the allowed target status,
        Then the inquiry status is updated.
        """
        inquiry = Inquiry.create(id=1, name="Alice", message="Hello")
        inquiry.status = initial_status

        inquiry.change_status(target_status)

        assert inquiry.status is target_status

    @pytest.mark.parametrize(
        ("initial_status", "target_status"),
        [
            (InquiryStatus.IN_PROGRESS, InquiryStatus.NEW),
            (InquiryStatus.CLOSED, InquiryStatus.NEW),
            (InquiryStatus.CLOSED, InquiryStatus.IN_PROGRESS),
        ],
    )
    def test_illegal_transition_from_non_terminal_is_rejected(
        self, initial_status, target_status
    ):
        """
        Given an inquiry in a non-terminal status,
        When changing to a forbidden target,
        Then IllegalInquiryTransitionError is raised with code "illegal_transition"
        and the inquiry status is not mutated.
        """
        from ordering.domain import IllegalInquiryTransitionError

        inquiry = Inquiry.create(id=1, name="Alice", message="Hello")
        inquiry.status = initial_status

        with pytest.raises(IllegalInquiryTransitionError) as exc_info:
            inquiry.change_status(target_status)

        assert exc_info.value.code == "illegal_transition"
        assert inquiry.status is initial_status

    @pytest.mark.parametrize(
        ("initial_status", "target_status"),
        [
            (InquiryStatus.ARCHIVED, InquiryStatus.NEW),
            (InquiryStatus.ARCHIVED, InquiryStatus.CLOSED),
        ],
    )
    def test_transition_from_archived_is_rejected(self, initial_status, target_status):
        """
        Given an inquiry in ARCHIVED (terminal) status,
        When attempting any status change,
        Then InquiryAlreadyTerminalError is raised with code "inquiry_already_terminal"
        and the inquiry status is not mutated.
        """
        from ordering.domain import InquiryAlreadyTerminalError

        inquiry = Inquiry.create(id=1, name="Alice", message="Hello")
        inquiry.status = initial_status

        with pytest.raises(InquiryAlreadyTerminalError) as exc_info:
            inquiry.change_status(target_status)

        assert exc_info.value.code == "inquiry_already_terminal"
        assert inquiry.status is initial_status

    def test_new_to_archived_directly_is_allowed(self):
        """
        Given an inquiry in NEW status,
        When archiving directly (skipping IN_PROGRESS and CLOSED),
        Then the transition succeeds — spam rejection path.
        """
        inquiry = Inquiry.create(id=1, name="Alice", message="Spam")
        inquiry.change_status(InquiryStatus.ARCHIVED)
        assert inquiry.status is InquiryStatus.ARCHIVED

    def test_archive_method_on_archived_raises(self):
        """
        Given an inquiry already in ARCHIVED status,
        When calling archive(),
        Then InquiryAlreadyTerminalError is raised.
        """
        from ordering.domain import InquiryAlreadyTerminalError

        inquiry = Inquiry.create(id=1, name="Alice", message="Hello")
        inquiry.status = InquiryStatus.ARCHIVED

        with pytest.raises(InquiryAlreadyTerminalError):
            inquiry.archive()

    def test_archive_method_transitions_from_new(self):
        """
        Given an inquiry in NEW,
        When calling archive(),
        Then status becomes ARCHIVED.
        """
        inquiry = Inquiry.create(id=1, name="Alice", message="Hello")
        inquiry.archive()
        assert inquiry.status is InquiryStatus.ARCHIVED

    def test_archive_method_transitions_from_closed(self):
        """
        Given an inquiry in CLOSED,
        When calling archive(),
        Then status becomes ARCHIVED.
        """
        inquiry = Inquiry.create(id=1, name="Alice", message="Hello")
        inquiry.status = InquiryStatus.CLOSED
        inquiry.archive()
        assert inquiry.status is InquiryStatus.ARCHIVED
