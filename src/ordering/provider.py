from dishka import Provider, Scope, provide

from ordering.config import OrderingConfig
from ordering.app.use_cases.place_order_uc import PlaceOrderUseCase
from ordering.app.use_cases.process_order_uc import ProcessOrderUseCase
from ordering.app.use_cases.delete_order_uc import DeleteOrderUseCase
from ordering.app.queries.get_orders_query import GetOrdersQuery
from ordering.app.interfaces.i_order_repo import IOrderRepo
from ordering.app.interfaces.i_notification_acl import INotificationAcl
from ordering.ports.driven.sql_order_repo import SqlOrderRepo
from ordering.ports.driven.system_notification_acl import SystemNotificationAcl
from ordering.ports.driving.facade import OrderingFacade


class OrderingProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> OrderingConfig:
        return OrderingConfig()

    repo = provide(SqlOrderRepo, provides=IOrderRepo)
    notification_acl = provide(SystemNotificationAcl, provides=INotificationAcl)

    place_uc = provide(PlaceOrderUseCase)
    process_uc = provide(ProcessOrderUseCase)
    delete_uc = provide(DeleteOrderUseCase)
    get_query = provide(GetOrdersQuery)

    facade = provide(OrderingFacade)
