"""Bulk change inquiry status. Per-row mutation through the runner;
domain errors become BulkFailure rows."""
from __future__ import annotations

from dataclasses import dataclass

from shared.app.bulk_runner import BulkRunner
# NOTE: BulkResultSchema/BulkTarget are shared ports layer types imported here
# by established project convention — see git log bulk_change_order_status_uc.py.
from shared.ports.driving.bulk_schemas import BulkResultSchema

from ..commands import BulkChangeInquiryStatusCommand
from ..errors import InquiryNotFoundError
from ..interfaces import IInquiryRepo
from ...domain import InvalidInquiryTransitionError, InquiryStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkChangeInquiryStatusUseCase:
    _repo: IInquiryRepo

    def __call__(self, cmd: BulkChangeInquiryStatusCommand) -> BulkResultSchema:
        def process_one(inquiry_id: int) -> None:
            inquiry = self._repo.get_by_id(int(inquiry_id))
            if inquiry is None:
                raise InquiryNotFoundError(int(inquiry_id))
            try:
                target = InquiryStatus(cmd.status)
            except ValueError:
                raise InvalidInquiryTransitionError.for_transition(
                    inquiry.status.value, cmd.status
                ) from None
            inquiry.change_status(target)
            self._repo.save(inquiry)

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_ids_by_filter,
        )
        return runner.run(cmd.target)
