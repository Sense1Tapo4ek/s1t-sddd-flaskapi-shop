from dishka import Provider, Scope, provide

from ordering.config import OrderingConfig
from ordering.app.use_cases.create_inquiry_uc import CreateInquiryUseCase
from ordering.app.use_cases.change_inquiry_status_uc import ChangeInquiryStatusUseCase
from ordering.app.use_cases.archive_inquiry_uc import ArchiveInquiryUseCase
from ordering.app.use_cases.bulk_change_inquiry_status_uc import (
    BulkChangeInquiryStatusUseCase,
)
from ordering.app.use_cases.place_order_uc import PlaceOrderUseCase
from ordering.app.use_cases.change_order_status_uc import ChangeOrderStatusUseCase
from ordering.app.use_cases.archive_order_uc import ArchiveOrderUseCase
from ordering.app.use_cases.bulk_change_order_status_uc import (
    BulkChangeOrderStatusUseCase,
    BulkArchiveOrderUseCase,
)
from ordering.app.use_cases.create_demo_data_uc import CreateDemoOrderingDataUseCase
from ordering.app.use_cases.create_test_order_uc import CreateTestOrderUseCase
from ordering.app.queries.get_inquiries_query import GetInquiriesQuery
from ordering.app.queries.get_order_by_id_query import GetOrderByIdQuery
from ordering.app.queries.get_orders_query import GetOrdersQuery
from ordering.app.interfaces.i_inquiry_repo import IInquiryRepo
from ordering.app.interfaces.i_notification_acl import INotificationAcl
from ordering.app.interfaces.i_order_repo import IOrderRepo
from ordering.app.interfaces.i_product_lookup_acl import IProductLookupACL
from ordering.ports.driven.sql_inquiry_repo import SqlInquiryRepo
from ordering.ports.driven.sql_order_repo import SqlOrderRepo
from ordering.ports.driven.system_notification_acl import SystemNotificationAcl
from ordering.ports.driven.catalog_product_lookup_acl import CatalogProductLookupACL
from ordering.ports.driving.inquiries_facade import InquiriesFacade
from ordering.ports.driving.orders_facade import OrdersFacade


class OrderingProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> OrderingConfig:
        return OrderingConfig()

    # ─── Inquiry wiring ───────────────────────────────────────────────
    inquiry_repo = provide(SqlInquiryRepo, provides=IInquiryRepo)
    notification_acl = provide(SystemNotificationAcl, provides=INotificationAcl)

    create_uc = provide(CreateInquiryUseCase)
    change_status_uc = provide(ChangeInquiryStatusUseCase)
    archive_uc = provide(ArchiveInquiryUseCase)
    bulk_status_uc = provide(BulkChangeInquiryStatusUseCase)
    get_query = provide(GetInquiriesQuery)

    facade = provide(InquiriesFacade)

    # ─── Order wiring ─────────────────────────────────────────────────
    order_repo = provide(SqlOrderRepo, provides=IOrderRepo)
    product_lookup_acl = provide(CatalogProductLookupACL, provides=IProductLookupACL)

    place_order_uc = provide(PlaceOrderUseCase)
    change_order_status_uc = provide(ChangeOrderStatusUseCase)
    archive_order_uc = provide(ArchiveOrderUseCase)
    bulk_order_status_uc = provide(BulkChangeOrderStatusUseCase)
    bulk_archive_order_uc = provide(BulkArchiveOrderUseCase)
    get_orders_query = provide(GetOrdersQuery)
    get_order_by_id_query = provide(GetOrderByIdQuery)

    # ─── Demo data wiring ─────────────────────────────────────────────
    demo_ordering_uc = provide(CreateDemoOrderingDataUseCase)
    test_order_uc = provide(CreateTestOrderUseCase)

    orders_facade = provide(OrdersFacade)
