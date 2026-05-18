from flask import jsonify, request, render_template
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from ordering.ports.driving.inquiries_facade import InquiriesFacade
from ordering.ports.driving.orders_facade import OrdersFacade
from ordering.ports.driving.schemas import (
    BulkInquiriesStatusIn,
    BulkOrdersStatusIn,
    InquiryStatusUpdateIn,
    OrderStatusUpdateIn,
)
from shared.adapters.driving.bulk import bulk_action_log, bulk_rate_limited
from shared.adapters.driving.middleware import permission_required
from shared.adapters.driving.htmx import render_partial_or_full
from shared.helpers.parsing import parse_table_params

# TODO: D2 — replace view_orders/manage_orders with view_inquiries/manage_inquiries
# when the new permissions are added to the access context (Stage 8 / D2).
ordering_admin_bp = APIBlueprint("ordering_admin", __name__, url_prefix="/admin/inquiries", enable_openapi=False)
orders_admin_bp = APIBlueprint("orders_admin", __name__, url_prefix="/admin/orders", enable_openapi=False)


@ordering_admin_bp.route("/")
@permission_required("view_orders")
@inject
def inquiries_page(facade: FromDishka[InquiriesFacade]):
    result = facade.list_inquiries(page=1, limit=20, sort_by="created_at", sort_dir="desc")
    return render_partial_or_full(
        "ordering/partials/table.html",
        "ordering/pages/orders.html",
        orders=result,
    )


@ordering_admin_bp.route("/table")
@permission_required("view_orders")
@inject
def inquiries_table(facade: FromDishka[InquiriesFacade]):
    params = parse_table_params(request.args)
    result = facade.list_inquiries(**params)
    return render_template("ordering/partials/table.html", orders=result)


@ordering_admin_bp.route("/search/schema")
@permission_required("view_orders")
@inject
def admin_search_schema(facade: FromDishka[InquiriesFacade]):
    return jsonify({
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
    })


@ordering_admin_bp.route("/<int:inquiry_id>/status", methods=["PATCH"])
@permission_required("manage_orders")
@inject
def update_inquiry_status(inquiry_id: int, facade: FromDishka[InquiriesFacade]):
    status = request.form.get("status")
    schema = InquiryStatusUpdateIn(status=status)
    facade.change_inquiry_status(inquiry_id, schema)
    result = facade.list_inquiries(page=1, limit=1, filters={"id__eq": str(inquiry_id)})
    order = result.items[0] if result.items else None
    return render_template("ordering/partials/row.html", order=order)


@ordering_admin_bp.route("/<int:inquiry_id>/archive", methods=["POST"])
@permission_required("manage_orders")
@inject
def archive_inquiry(inquiry_id: int, facade: FromDishka[InquiriesFacade]):
    facade.archive_inquiry(inquiry_id)
    result = facade.list_inquiries(page=1, limit=1, filters={"id__eq": str(inquiry_id)})
    order = result.items[0] if result.items else None
    return render_template("ordering/partials/row.html", order=order)


@ordering_admin_bp.route("/test", methods=["POST"])
@permission_required("manage_orders")
@inject
def create_test_inquiry(facade: FromDishka[InquiriesFacade]):
    from ordering.ports.driving.schemas import InquiryIn

    schema = InquiryIn(name="Тестовый клиент", phone="+375291234567", message="Тестовое обращение")
    facade.create_inquiry(schema)
    params = parse_table_params(request.args)
    result = facade.list_inquiries(**params)
    return render_template(
        "ordering/partials/table.html",
        orders=result,
    ), 200, {"HX-Trigger": '{"showToast":{"message":"Тестовое обращение создано","type":"success"}}'}


@ordering_admin_bp.route("/badge")
@permission_required("view_orders")
@inject
def inquiries_badge(facade: FromDishka[InquiriesFacade]):
    result = facade.list_inquiries(page=1, limit=1, filters={"status__eq": "new"})
    count = result.total
    if count > 0:
        return f'<span class="badge badge--new">{count}</span>'
    return '<span></span>'


# ─── Bulk actions ───────────────────────────────────────────────────


@ordering_admin_bp.route("/bulk/status", methods=["POST"])
@permission_required("manage_orders")
@bulk_rate_limited("inquiries.bulk_change_status")
@bulk_action_log("inquiries.bulk_change_status")
@inject
def inquiries_bulk_status(facade: FromDishka[InquiriesFacade]):
    payload = BulkInquiriesStatusIn.model_validate(request.get_json(silent=True) or {})
    result = facade.bulk_change_inquiries_status(payload)
    return jsonify(result.model_dump(mode="json")), 200


@ordering_admin_bp.route("/bulk/archive", methods=["POST"])
@permission_required("manage_orders")
@bulk_rate_limited("inquiries.bulk_archive")
@bulk_action_log("inquiries.bulk_archive")
@inject
def inquiries_bulk_archive(facade: FromDishka[InquiriesFacade]):
    from ordering.ports.driving.schemas import BulkInquiriesStatusIn as _BulkIn
    payload = _BulkIn.model_validate({**(request.get_json(silent=True) or {}), "status": "archived"})
    result = facade.bulk_change_inquiries_status(payload)
    return jsonify(result.model_dump(mode="json")), 200


# ─── Orders admin routes ──────────────────────────────────────────────────────


@orders_admin_bp.route("/")
@permission_required("view_orders")
@inject
def orders_page(facade: FromDishka[OrdersFacade]):
    result = facade.list_orders(page=1, limit=20, sort_by="created_at", sort_dir="desc")
    return render_partial_or_full(
        "ordering/partials/orders_table.html",
        "ordering/pages/orders_list.html",
        orders=result,
    )


@orders_admin_bp.route("/table")
@permission_required("view_orders")
@inject
def orders_table(facade: FromDishka[OrdersFacade]):
    params = parse_table_params(request.args)
    result = facade.list_orders(**params)
    return render_template("ordering/partials/orders_table.html", orders=result)


@orders_admin_bp.route("/search/schema")
@permission_required("view_orders")
@inject
def orders_search_schema(facade: FromDishka[OrdersFacade]):
    return jsonify({
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
    })


@orders_admin_bp.route("/badge")
@permission_required("view_orders")
@inject
def orders_badge(facade: FromDishka[OrdersFacade]):
    result = facade.list_orders(page=1, limit=1, filters={"status__eq": "new"})
    count = result.total
    if count > 0:
        return f'<span class="badge badge--new">{count}</span>'
    return '<span></span>'


@orders_admin_bp.route("/<int:order_id>/status", methods=["PATCH"])
@permission_required("manage_orders")
@inject
def update_order_status(order_id: int, facade: FromDishka[OrdersFacade]):
    status = request.form.get("status") or (request.get_json(silent=True) or {}).get("status")
    schema = OrderStatusUpdateIn(status=status)
    facade.change_order_status(order_id, schema)
    return jsonify({"success": True})


@orders_admin_bp.route("/<int:order_id>/archive", methods=["POST"])
@permission_required("manage_orders")
@inject
def archive_order(order_id: int, facade: FromDishka[OrdersFacade]):
    facade.archive_order(order_id)
    return jsonify({"success": True})


@orders_admin_bp.route("/bulk/status", methods=["POST"])
@permission_required("manage_orders")
@bulk_rate_limited("orders.bulk_change_status")
@bulk_action_log("orders.bulk_change_status")
@inject
def orders_bulk_status(facade: FromDishka[OrdersFacade]):
    payload = BulkOrdersStatusIn.model_validate(request.get_json(silent=True) or {})
    result = facade.bulk_change_orders_status(payload)
    return jsonify(result.model_dump(mode="json")), 200


@orders_admin_bp.route("/bulk/archive", methods=["POST"])
@permission_required("manage_orders")
@bulk_rate_limited("orders.bulk_archive")
@bulk_action_log("orders.bulk_archive")
@inject
def orders_bulk_archive(facade: FromDishka[OrdersFacade]):
    payload = BulkOrdersStatusIn.model_validate(
        {**(request.get_json(silent=True) or {}), "status": "archived"}
    )
    result = facade.bulk_change_orders_status(payload)
    return jsonify(result.model_dump(mode="json")), 200
