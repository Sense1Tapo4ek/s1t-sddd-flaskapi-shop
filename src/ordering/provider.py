from dishka import Provider, Scope, provide

from ordering.config import OrderingConfig
from ordering.app.use_cases.create_inquiry_uc import CreateInquiryUseCase
from ordering.app.use_cases.change_inquiry_status_uc import ChangeInquiryStatusUseCase
from ordering.app.use_cases.archive_inquiry_uc import ArchiveInquiryUseCase
from ordering.app.use_cases.bulk_change_inquiry_status_uc import (
    BulkChangeInquiryStatusUseCase,
)
from ordering.app.queries.get_inquiries_query import GetInquiriesQuery
from ordering.app.interfaces.i_inquiry_repo import IInquiryRepo
from ordering.app.interfaces.i_notification_acl import INotificationAcl
from ordering.ports.driven.sql_inquiry_repo import SqlInquiryRepo
from ordering.ports.driven.system_notification_acl import SystemNotificationAcl
from ordering.ports.driving.inquiries_facade import InquiriesFacade


class OrderingProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> OrderingConfig:
        return OrderingConfig()

    repo = provide(SqlInquiryRepo, provides=IInquiryRepo)
    notification_acl = provide(SystemNotificationAcl, provides=INotificationAcl)

    create_uc = provide(CreateInquiryUseCase)
    change_status_uc = provide(ChangeInquiryStatusUseCase)
    archive_uc = provide(ArchiveInquiryUseCase)
    bulk_status_uc = provide(BulkChangeInquiryStatusUseCase)
    get_query = provide(GetInquiriesQuery)

    facade = provide(InquiriesFacade)
