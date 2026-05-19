from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from shared.generics.pagination import PaginationParams

from ..interfaces import IInquiryRepo, IOrderRepo, IProductLookupACL
from ..interfaces.i_product_lookup_acl import ProductSnapshot
from ...domain import (
    DeliveryInfo,
    DeliveryMethod,
    Inquiry,
    InquiryStatus,
    Order,
    OrderItem,
    OrderStatus,
)


_DEMO_INQUIRIES: list[dict[str, Any]] = [
    {
        "name": "Анна Иванова",
        "phone": "+375 29 123-45-67",
        "contact_email": "anna.ivanova@example.com",
        "message": "Здравствуйте! Подскажите, есть ли в наличии платье размер M? Хотела бы посмотреть в шоуруме.",
        "status": InquiryStatus.NEW,
    },
    {
        "name": "Дмитрий Петров",
        "phone": "+375 33 987-65-43",
        "contact_email": None,
        "message": "Нужна консультация по выбору обуви для бега. Бюджет до 200 руб.",
        "status": InquiryStatus.NEW,
    },
    {
        "name": "Ольга",
        "phone": None,
        "contact_email": "olga.k@example.com",
        "message": "Можно ли оформить доставку курьером в Минск в субботу до 12:00?",
        "status": InquiryStatus.NEW,
    },
    {
        "name": "Сергей Козлов",
        "phone": "+375 44 222-11-00",
        "contact_email": "kozlov.s@example.com",
        "message": "Заказ #142 — когда ожидать звонок от менеджера? Уже сутки прошло.",
        "status": InquiryStatus.IN_PROGRESS,
    },
    {
        "name": "Мария",
        "phone": "+375 25 555-77-88",
        "contact_email": None,
        "message": "Спасибо за быструю доставку, всё подошло.",
        "status": InquiryStatus.CLOSED,
    },
]


_DEMO_ORDERS: list[dict[str, Any]] = [
    {
        "customer_user_id": 900001,
        "contact_email": "anna.ivanova@example.com",
        "contact_phone": "+375 29 123-45-67",
        "items": [{"qty": 1}, {"qty": 2}],
        "delivery_method": "pickup",
        "address": "",
        "delivery_comment": "Заберу сегодня после 18:00",
        "comment": "Если будет коробка — упакуйте, пожалуйста.",
        "final_status": OrderStatus.NEW,
    },
    {
        "customer_user_id": 900001,
        "contact_email": "anna.ivanova@example.com",
        "contact_phone": "+375 29 123-45-67",
        "items": [{"qty": 1}],
        "delivery_method": "courier",
        "address": "г. Минск, пр. Независимости, 56, кв. 12",
        "delivery_comment": "Домофон 12К, позвонить за 15 минут",
        "comment": "",
        "final_status": OrderStatus.NEW,
    },
    {
        "customer_user_id": 900002,
        "contact_email": "kozlov.s@example.com",
        "contact_phone": "+375 44 222-11-00",
        "items": [{"qty": 3}],
        "delivery_method": "courier",
        "address": "г. Гомель, ул. Советская, 21",
        "delivery_comment": "",
        "comment": "Оплата при получении наличными",
        "final_status": OrderStatus.CONFIRMED,
    },
    {
        "customer_user_id": 900003,
        "contact_email": "olga.k@example.com",
        "contact_phone": "+375 25 777-11-22",
        "items": [{"qty": 1}, {"qty": 1}, {"qty": 2}],
        "delivery_method": "pickup",
        "address": "",
        "delivery_comment": "",
        "comment": "",
        "final_status": OrderStatus.COMPLETED,
    },
    {
        "customer_user_id": 900004,
        "contact_email": "",
        "contact_phone": "+375 33 555-00-77",
        "items": [{"qty": 1}],
        "delivery_method": "courier",
        "address": "г. Брест, ул. Ленина, 7",
        "delivery_comment": "",
        "comment": "Передумал, отмените, пожалуйста.",
        "final_status": OrderStatus.CANCELED,
    },
    {
        "customer_user_id": 900005,
        "contact_email": "maria@example.com",
        "contact_phone": "+375 25 555-77-88",
        "items": [{"qty": 2}, {"qty": 1}],
        "delivery_method": "pickup",
        "address": "",
        "delivery_comment": "",
        "comment": "",
        "final_status": OrderStatus.NEW,
    },
]


@dataclass(frozen=True, slots=True)
class DemoOrderingResult:
    inquiries_created: int = 0
    orders_created: int = 0
    skipped: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"success": True, **asdict(self)}


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDemoOrderingDataUseCase:
    _orders: IOrderRepo
    _inquiries: IInquiryRepo
    _product_acl: IProductLookupACL

    def __call__(self) -> DemoOrderingResult:
        inquiries_created = self._seed_inquiries()
        orders_created = self._seed_orders()
        skipped = inquiries_created == 0 and orders_created == 0
        return DemoOrderingResult(
            inquiries_created=inquiries_created,
            orders_created=orders_created,
            skipped=skipped,
        )

    def _seed_inquiries(self) -> int:
        existing = self._inquiries.get_paginated(
            PaginationParams(page=1, limit=1, filters={})
        )
        if existing.total > 0:
            return 0

        created = 0
        for cfg in _DEMO_INQUIRIES:
            inquiry = Inquiry.create(
                id=0,
                name=cfg["name"],
                message=cfg["message"],
                phone=cfg["phone"],
                contact_email=cfg["contact_email"],
            )
            target_status: InquiryStatus = cfg["status"]
            if target_status is not InquiryStatus.NEW:
                inquiry.change_status(target_status)
            self._inquiries.save(inquiry)
            created += 1
        return created

    def _seed_orders(self) -> int:
        existing = self._orders.get_paginated(
            PaginationParams(page=1, limit=1, filters={})
        )
        if existing.total > 0:
            return 0

        products = self._sample_products()
        if not products:
            return 0

        created = 0
        for index, cfg in enumerate(_DEMO_ORDERS):
            items = [
                OrderItem(
                    product_id=products[(index + position) % len(products)].id,
                    title_snapshot=products[(index + position) % len(products)].title,
                    unit_price=products[(index + position) % len(products)].unit_price,
                    quantity=item_cfg["qty"],
                )
                for position, item_cfg in enumerate(cfg["items"])
            ]
            delivery = DeliveryInfo(
                method=DeliveryMethod(cfg["delivery_method"]),
                address=cfg["address"],
                comment=cfg["delivery_comment"],
            )
            order = Order.place(
                customer_user_id=cfg["customer_user_id"],
                items=items,
                delivery=delivery,
                contact_phone=cfg["contact_phone"],
                contact_email=cfg["contact_email"],
                comment=cfg["comment"],
            )
            self._orders.save(order)
            self._advance_status(order, cfg["final_status"])
            created += 1
        return created

    def _advance_status(self, order: Order, final: OrderStatus) -> None:
        path = _STATUS_PATHS.get(final)
        if not path:
            return
        for step in path:
            order.change_status(step)
            self._orders.save(order)

    def _sample_products(self, target: int = 6, scan_limit: int = 400) -> list[ProductSnapshot]:
        found: list[ProductSnapshot] = []
        for product_id in range(1, scan_limit + 1):
            snap = self._product_acl.get(product_id)
            if snap is None or not snap.is_active:
                continue
            found.append(snap)
            if len(found) >= target:
                break
        return found


_STATUS_PATHS: dict[OrderStatus, tuple[OrderStatus, ...]] = {
    OrderStatus.NEW: (),
    OrderStatus.CONFIRMED: (OrderStatus.CONFIRMED,),
    OrderStatus.COMPLETED: (OrderStatus.CONFIRMED, OrderStatus.COMPLETED),
    OrderStatus.CANCELED: (OrderStatus.CANCELED,),
    OrderStatus.ARCHIVED: (OrderStatus.ARCHIVED,),
}
