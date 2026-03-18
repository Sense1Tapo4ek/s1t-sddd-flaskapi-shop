import json
from flask import request, render_template, make_response
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from catalog.ports.driving.facade import CatalogFacade
from shared.adapters.driving.middleware import jwt_required
from shared.adapters.driving.htmx import render_partial_or_full

catalog_admin_bp = APIBlueprint("catalog_admin", __name__, url_prefix="/admin/products")


@catalog_admin_bp.route("/")
@jwt_required
@inject
def products_page(facade: FromDishka[CatalogFacade]):
    result = facade.search_products(page=1, limit=20, sort_by="created_at", sort_dir="desc")
    return render_partial_or_full(
        "catalog/partials/table.html",
        "catalog/pages/products.html",
        products=result,
    )


@catalog_admin_bp.route("/table")
@jwt_required
@inject
def products_table(facade: FromDishka[CatalogFacade]):
    params = _parse_table_params(request.args)
    result = facade.search_products(**params)
    return render_template("catalog/partials/table.html", products=result)


@catalog_admin_bp.route("/new")
@jwt_required
def product_page_new():
    return render_template("catalog/pages/product_form.html", product_id=None)


@catalog_admin_bp.route("/<int:product_id>/edit")
@jwt_required
def product_page_edit(product_id: int):
    return render_template("catalog/pages/product_form.html", product_id=product_id)


@catalog_admin_bp.route("/form/new")
@jwt_required
def product_form_new():
    return render_template("catalog/partials/form.html", product=None)


@catalog_admin_bp.route("/<int:product_id>/form")
@jwt_required
@inject
def product_form_edit(product_id: int, facade: FromDishka[CatalogFacade]):
    product = facade.get_detail(product_id)
    return render_template("catalog/partials/form.html", product=product)


@catalog_admin_bp.route("/", methods=["POST"])
@jwt_required
@inject
def create_product(facade: FromDishka[CatalogFacade]):
    title = request.form.get("title", "")
    price = float(request.form.get("price", 0))
    description = request.form.get("description", "")
    images = [
        (file.filename or "img.jpg", file.read())
        for file in request.files.getlist("images")
    ]
    facade.create_product(title=title, price=price, description=description, images=images)
    params = _parse_table_params(request.args)
    table_result = facade.search_products(**params)
    response = make_response(
        render_template("catalog/partials/table.html", products=table_result)
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Product created", "type": "success"},
        "closeModal": True,
    })
    return response


@catalog_admin_bp.route("/<int:product_id>", methods=["PUT"])
@jwt_required
@inject
def update_product(product_id: int, facade: FromDishka[CatalogFacade]):
    kwargs = {}
    if "title" in request.form:
        kwargs["title"] = request.form["title"]
    if "price" in request.form:
        kwargs["price"] = float(request.form["price"])
    if "description" in request.form:
        kwargs["description"] = request.form["description"]
    new_images = [
        (file.filename or "img.jpg", file.read())
        for file in request.files.getlist("new_images")
    ]
    if new_images:
        kwargs["new_images"] = new_images
    deleted = request.form.getlist("deleted_images")
    if deleted:
        kwargs["deleted_images"] = deleted
    result = facade.update_product(product_id, **kwargs)
    response = make_response(
        render_template("catalog/partials/form.html", product=result)
    )
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": "Product updated", "type": "success"},
    })
    return response


@catalog_admin_bp.route("/<int:product_id>", methods=["DELETE"])
@jwt_required
@inject
def delete_product(product_id: int, facade: FromDishka[CatalogFacade]):
    facade.delete_product(product_id)
    return "", 200


def _parse_table_params(args) -> dict:
    return {
        "page": int(args.get("page", 1)),
        "limit": int(args.get("limit", 20)),
        "sort_by": args.get("sort_by", "created_at"),
        "sort_dir": args.get("sort_dir", "desc"),
        "filters": {k: v for k, v in args.items()
                     if "__" in k and k not in ("sort_by", "sort_dir")},
    }
