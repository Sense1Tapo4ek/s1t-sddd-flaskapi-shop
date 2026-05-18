from dataclasses import dataclass

from ..interfaces import IInquiryRepo
from ..commands import ChangeInquiryStatusCommand
from ..errors import InquiryNotFoundError
from ...domain import InvalidInquiryTransitionError, InquiryStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeInquiryStatusUseCase:
    _repo: IInquiryRepo

    def __call__(self, cmd: ChangeInquiryStatusCommand) -> int:
        inquiry = self._repo.get_by_id(cmd.inquiry_id)
        if inquiry is None:
            raise InquiryNotFoundError(cmd.inquiry_id)

        # Domain Logic
        try:
            new_status = InquiryStatus(cmd.new_status)
        except ValueError:
            raise InvalidInquiryTransitionError.for_transition(inquiry.status.value, cmd.new_status) from None
        inquiry.change_status(new_status)

        # Persist
        self._repo.save(inquiry)

        return inquiry.id
