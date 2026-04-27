from flask import request, render_template
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from ordering.ports.driving.facade import OrderingFacade
from ordering.ports.driving.schemas import OrderStatusUpdateIn
from shared.adapters.driving.middleware import permission_required
from shared.adapters.driving.htmx import render_partial_or_full
from shared.helpers.parsing import parse_table_params

ordering_admin_bp = APIBlueprint("ordering_admin", __name__, url_prefix="/admin/orders", enable_openapi=False)


@ordering_admin_bp.route("/")
@permission_required("view_orders")
@inject
def orders_page(facade: FromDishka[OrderingFacade]):
    result = facade.list_orders(page=1, limit=20, sort_by="created_at", sort_dir="desc")
    return render_partial_or_full(
        "ordering/partials/table.html",
        "ordering/pages/orders.html",
        orders=result,
    )


@ordering_admin_bp.route("/table")
@permission_required("view_orders")
@inject
def orders_table(facade: FromDishka[OrderingFacade]):
    params = parse_table_params(request.args)
    result = facade.list_orders(**params)
    return render_template("ordering/partials/table.html", orders=result)


@ordering_admin_bp.route("/<int:order_id>/status", methods=["PATCH"])
@permission_required("manage_orders")
@inject
def update_status(order_id: int, facade: FromDishka[OrderingFacade]):
    status = request.form.get("status")
    schema = OrderStatusUpdateIn(status=status)
    facade.process_order(order_id, schema)
    result = facade.list_orders(page=1, limit=1, filters={"id__eq": str(order_id)})
    order = result.items[0] if result.items else None
    return render_template("ordering/partials/row.html", order=order)


@ordering_admin_bp.route("/test", methods=["POST"])
@permission_required("manage_orders")
@inject
def create_test_order(facade: FromDishka[OrderingFacade]):
    from ordering.ports.driving.schemas import OrderIn

    schema = OrderIn(name="Test Customer", phone="+375291234567", comment="Test order")
    facade.place_order(schema)
    params = parse_table_params(request.args)
    result = facade.list_orders(**params)
    return render_template(
        "ordering/partials/table.html",
        orders=result,
    ), 200, {"HX-Trigger": '{"showToast":{"message":"Test order created","type":"success"}}'}


@ordering_admin_bp.route("/badge")
@permission_required("view_orders")
@inject
def orders_badge(facade: FromDishka[OrderingFacade]):
    result = facade.list_orders(page=1, limit=1, filters={"status__eq": "new"})
    count = result.total
    if count > 0:
        return f'<span class="badge badge--new">{count}</span>'
    return '<span></span>'

