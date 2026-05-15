from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka
from flask import request

from shared.adapters.driving.middleware import permission_required
from ordering.ports.driving import (
    OrderingFacade,
    OrderIn,
    OrderStatusUpdateIn,
    OrderSearchQuery,
)

ordering_bp = APIBlueprint("ordering", __name__, url_prefix="/orders")


# --- PUBLIC ---


@ordering_bp.post("")
@ordering_bp.input(OrderIn)
@ordering_bp.doc(
    summary="Создать новый заказ (Public)",
    description="Создаёт новый заказ покупателя. При успешном создании отправляет уведомления в Telegram активным владельцу/суперадмину, если бот настроен.",
)
@inject
def place_order(json_data: OrderIn, facade: FromDishka[OrderingFacade]):
    order_id = facade.place_order(json_data)
    return {"success": True, "id": order_id}, 201


# --- ADMIN (Protected) ---


@ordering_bp.get("")
@permission_required("view_orders")
@ordering_bp.input(OrderSearchQuery, location="query")
@ordering_bp.doc(
    summary="Список заказов (ADMIN ONLY)",
    description="Возвращает постраничный список всех заказов с сортировкой и фильтрацией.",
    security="JWTAuth",
)
@inject
def list_orders(query_data: OrderSearchQuery, facade: FromDishka[OrderingFacade]):
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


@ordering_bp.get("/search/schema")
@permission_required("view_orders")
@ordering_bp.doc(
    summary="Схема фильтров заказов (ADMIN ONLY)",
    description="Возвращает доступные конфигурации полей и варианты статусов для построения фильтров заказов.",
    security="JWTAuth",
)
@inject
def admin_search_schema(facade: FromDishka[OrderingFacade]):
    return {
        "fields": [
            {"key": "id", "label": "ID", "type": "number", "operators": ["eq"]},
            {"key": "name", "label": "Имя", "type": "string", "operators": ["ilike", "eq"]},
            {"key": "phone", "label": "Телефон", "type": "string", "operators": ["ilike", "eq"]},
            {"key": "created_at", "label": "Дата", "type": "date", "operators": ["eq", "gte", "lte"]},
            {
                "key": "status",
                "label": "Статус",
                "type": "enum",
                "operators": ["eq"],
                "options": [
                    {"value": "new", "label": "Новый"},
                    {"value": "processing", "label": "В обработке"},
                    {"value": "done", "label": "Выполнен"},
                    {"value": "canceled", "label": "Отменён"},
                ],
            },
        ]
    }


@ordering_bp.patch("/<int:order_id>/status")
@permission_required("manage_orders")
@ordering_bp.input(OrderStatusUpdateIn)
@ordering_bp.doc(
    summary="Обновить статус заказа (ADMIN ONLY)",
    description="Переводит заказ в новый статус с доменной валидацией.",
    security="JWTAuth",
)
@inject
def update_status(order_id: int, json_data: OrderStatusUpdateIn, facade: FromDishka[OrderingFacade]):
    facade.process_order(order_id, json_data)
    return {"success": True}


@ordering_bp.delete("/<int:order_id>")
@permission_required("manage_orders")
@ordering_bp.doc(
    summary="Удалить заказ (ADMIN ONLY)",
    description="Безвозвратно удаляет заказ из системы.",
    security="JWTAuth",
)
@inject
def delete_order(order_id: int, facade: FromDishka[OrderingFacade]):
    facade.delete_order(order_id)
    return {"success": True}
