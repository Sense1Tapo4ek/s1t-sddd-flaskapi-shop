from dataclasses import dataclass

from ..interfaces import IInquiryRepo
from ..commands import ArchiveInquiryCommand
from ..errors import InquiryNotFoundError


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchiveInquiryUseCase:
    _repo: IInquiryRepo

    def __call__(self, cmd: ArchiveInquiryCommand) -> int:
        inquiry = self._repo.get_by_id(cmd.inquiry_id)
        if inquiry is None:
            raise InquiryNotFoundError(cmd.inquiry_id)

        # archive() raises InquiryAlreadyTerminalError if already ARCHIVED
        inquiry.archive()

        # Persist
        self._repo.save(inquiry)

        return inquiry.id
