from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka
from flask import request

from shared.adapters.driving.bulk import bulk_rate_limited
from shared.adapters.driving.middleware import (
    customer_required,
    current_customer_id,
    permission_required,
)
from ordering.ports.driving import (
    InquiriesFacade,
    InquiryIn,
    InquiryStatusUpdateIn,
    InquirySearchQuery,
    OrdersFacade,
    OrderIn,
    OrderStatusUpdateIn,
    OrderSearchQuery,
)

ordering_bp = APIBlueprint("ordering", __name__, url_prefix="/inquiries")
orders_bp = APIBlueprint("orders", __name__, url_prefix="/orders")


# --- PUBLIC ---


@ordering_bp.post("")
@ordering_bp.input(InquiryIn)
@ordering_bp.doc(
    summary="Создать новое обращение (Public)",
    description="Создаёт новое контактное обращение от посетителя. При успешном создании отправляет уведомления в Telegram активным владельцу/суперадмину, если бот настроен.",
)
@bulk_rate_limited("inquiries.create")
@inject
def create_inquiry(json_data: InquiryIn, facade: FromDishka[InquiriesFacade]):
    inquiry_id = facade.create_inquiry(json_data)
    return {"success": True, "id": inquiry_id}, 201


# --- ADMIN (Protected) ---


@ordering_bp.get("")
@permission_required("view_orders")
@ordering_bp.input(InquirySearchQuery, location="query")
@ordering_bp.doc(
    summary="Список обращений (ADMIN ONLY)",
    description="Возвращает постраничный список всех обращений с сортировкой и фильтрацией.",
    security="JWTAuth",
)
@inject
def list_inquiries(query_data: InquirySearchQuery, facade: FromDishka[InquiriesFacade]):
    raw_query_dict = request.args.to_dict()
    reserved_keys = {"page", "limit", "sort_by", "sort_dir"}

    filters = {k: v for k, v in raw_query_dict.items() if k not in reserved_keys and v != ""}

    result = facade.list_inquiries(
        page=query_data.page,
        limit=query_data.limit,
        sort_by=query_data.sort_by,
        sort_dir=query_data.sort_dir,
        filters=filters,
    )
    return result.model_dump()


@ordering_bp.get("/search/schema")
@permission_required("view_orders")
@ordering_bp.doc(
    summary="Схема фильтров обращений (ADMIN ONLY)",
    description="Возвращает доступные конфигурации полей и варианты статусов для построения фильтров обращений.",
    security="JWTAuth",
)
@inject
def admin_search_schema(facade: FromDishka[InquiriesFacade]):
    return {
        "fields": [
            {"key": "id", "label": "ID", "type": "number", "operators": ["eq"]},
            {"key": "name", "label": "Имя", "type": "string", "operators": ["ilike", "eq"]},
            {"key": "phone", "label": "Телефон", "type": "string", "operators": ["ilike", "eq"]},
            {"key": "contact_email", "label": "Email", "type": "string", "operators": ["ilike", "eq"]},
            {"key": "created_at", "label": "Дата", "type": "date", "operators": ["eq", "gte", "lte"]},
            {
                "key": "status",
                "label": "Статус",
                "type": "enum",
                "operators": ["eq"],
                "options": [
                    {"value": "new", "label": "Новое"},
                    {"value": "in_progress", "label": "В обработке"},
                    {"value": "closed", "label": "Закрыто"},
                    {"value": "archived", "label": "Архив"},
                ],
            },
        ]
    }


@ordering_bp.patch("/<int:inquiry_id>/status")
@permission_required("manage_orders")
@ordering_bp.input(InquiryStatusUpdateIn)
@ordering_bp.doc(
    summary="Обновить статус обращения (ADMIN ONLY)",
    description="Переводит обращение в новый статус с доменной валидацией.",
    security="JWTAuth",
)
@inject
def update_inquiry_status(inquiry_id: int, json_data: InquiryStatusUpdateIn, facade: FromDishka[InquiriesFacade]):
    facade.change_inquiry_status(inquiry_id, json_data)
    return {"success": True}


@ordering_bp.post("/<int:inquiry_id>/archive")
@permission_required("manage_orders")
@ordering_bp.doc(
    summary="Архивировать обращение (ADMIN ONLY)",
    description="Переводит обращение в статус ARCHIVED.",
    security="JWTAuth",
)
@inject
def archive_inquiry(inquiry_id: int, facade: FromDishka[InquiriesFacade]):
    facade.archive_inquiry(inquiry_id)
    return {"success": True}


# ─── Orders (customer) ────────────────────────────────────────────────────────


@orders_bp.post("")
@orders_bp.input(OrderIn)
@orders_bp.doc(
    summary="Разместить заказ (Customer)",
    description="Создаёт заказ от авторизованного покупателя. customer_user_id берётся из JWT.",
    security="JWTAuth",
)
@customer_required
@inject
def place_order(json_data: OrderIn, facade: FromDishka[OrdersFacade]):
    customer_user_id = current_customer_id()
    order_id = facade.place_order(json_data, customer_user_id)
    return {"success": True, "id": order_id}, 201


# ─── Orders (admin) ───────────────────────────────────────────────────────────


@orders_bp.get("")
@permission_required("view_orders")
@orders_bp.input(OrderSearchQuery, location="query")
@orders_bp.doc(
    summary="Список заказов (ADMIN ONLY)",
    security="JWTAuth",
)
@inject
def list_orders(query_data: OrderSearchQuery, facade: FromDishka[OrdersFacade]):
    raw_query_dict = request.args.to_dict()
    reserved_keys = {"page", "limit", "sort_by", "sort_dir"}
    filters = {k: v for k, v in raw_query_dict.items() if k not in reserved_keys and v != ""}
    result = facade.list_orders(
        page=query_data.page,
        limit=query_data.limit,
        sort_by=query_data.sort_by,
        sort_dir=query_data.sort_dir,
        filters=filters,
    )
    return result.model_dump()


@orders_bp.get("/search/schema")
@permission_required("view_orders")
@orders_bp.doc(summary="Схема фильтров заказов (ADMIN ONLY)", security="JWTAuth")
@inject
def orders_search_schema(facade: FromDishka[OrdersFacade]):
    return {
        "fields": [
            {"key": "id", "label": "ID", "type": "number", "operators": ["eq"]},
            {"key": "customer_user_id", "label": "Customer ID", "type": "number", "operators": ["eq"]},
            {"key": "created_at", "label": "Дата", "type": "date", "operators": ["eq", "gte", "lte"]},
            {
                "key": "status",
                "label": "Статус",
                "type": "enum",
                "operators": ["eq"],
                "options": [
                    {"value": "new", "label": "Новый"},
                    {"value": "confirmed", "label": "Подтверждён"},
                    {"value": "completed", "label": "Выполнен"},
                    {"value": "canceled", "label": "Отменён"},
                    {"value": "archived", "label": "Архив"},
                ],
            },
        ]
    }


@orders_bp.patch("/<int:order_id>/status")
@permission_required("manage_orders")
@orders_bp.input(OrderStatusUpdateIn)
@orders_bp.doc(summary="Обновить статус заказа (ADMIN ONLY)", security="JWTAuth")
@inject
def update_order_status(order_id: int, json_data: OrderStatusUpdateIn, facade: FromDishka[OrdersFacade]):
    facade.change_order_status(order_id, json_data)
    return {"success": True}


@orders_bp.post("/<int:order_id>/archive")
@permission_required("manage_orders")
@orders_bp.doc(summary="Архивировать заказ (ADMIN ONLY)", security="JWTAuth")
@inject
def archive_order(order_id: int, facade: FromDishka[OrdersFacade]):
    facade.archive_order(order_id)
    return {"success": True}
