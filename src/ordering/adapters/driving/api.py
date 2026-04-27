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
    summary="Place new order (Public)",
    description="Creates a new customer order. On success, sends notifications to active owner/superadmin Telegram chat IDs when the bot is configured.",
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
    summary="List orders (ADMIN ONLY)",
    description="Returns a paginated list of all orders with sorting and filtering.",
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
    summary="Order filter schema (ADMIN ONLY)",
    description="Returns available field configs and status options for building order filters.",
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
    summary="Update order status (ADMIN ONLY)",
    description="Transitions an order to a new status with domain validation.",
    security="JWTAuth",
)
@inject
def update_status(order_id: int, json_data: OrderStatusUpdateIn, facade: FromDishka[OrderingFacade]):
    facade.process_order(order_id, json_data)
    return {"success": True}


@ordering_bp.delete("/<int:order_id>")
@permission_required("manage_orders")
@ordering_bp.doc(
    summary="Delete order (ADMIN ONLY)",
    description="Permanently removes an order from the system.",
    security="JWTAuth",
)
@inject
def delete_order(order_id: int, facade: FromDishka[OrderingFacade]):
    facade.delete_order(order_id)
    return {"success": True}
