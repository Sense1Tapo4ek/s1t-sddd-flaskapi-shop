import json
from flask import request, render_template, make_response, redirect
from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka

from catalog.ports.driving.facade import CatalogFacade
from shared.adapters.driving.middleware import any_permission_required, permission_required
from shared.adapters.driving.htmx import render_partial_or_full
from shared.helpers.parsing import parse_optional_int, safe_float, parse_table_params

catalog_admin_bp = APIBlueprint("catalog_admin", __name__, url_prefix="/admin/products", enable_openapi=False)
taxonomy_admin_bp = APIBlueprint("catalog_taxonomy_admin", __name__, url_prefix="/admin", enable_openapi=False)


@catalog_admin_bp.route("/")
@permission_required("view_products")
def products_page():
    return redirect("/admin/catalog/?view=products")


@catalog_admin_bp.route("/legacy")
@permission_required("view_products")
@inject
def legacy_products_page(facade: FromDishka[CatalogFacade]):
    result = facade.search_products(page=1, limit=20, sort_by="created_at", sort_dir="desc")
    return render_partial_or_full(
        "catalog/partials/table.html",
        "catalog/pages/products.html",
        products=result,
    )


@catalog_admin_bp.route("/table")
@permission_required("view_products")
@inject
def products_table(facade: FromDishka[CatalogFacade]):
    params = parse_table_params(request.args)
    result = facade.search_products(**params)
    return render_template("catalog/partials/table.html", products=result)


@catalog_admin_bp.route("/new")
@permission_required("edit_products")
def product_page_new():
    category_id = parse_optional_int(request.args.get("category_id"), "category_id")
    return render_template(
        "catalog/pages/product_form.html",
        product_id=None,
        initial_category_id=category_id,
    )


@catalog_admin_bp.route("/<int:product_id>/edit")
@permission_required("edit_products")
def product_page_edit(product_id: int):
    category_id = parse_optional_int(request.args.get("category_id"), "category_id")
    return render_template(
        "catalog/pages/product_form.html",
        product_id=product_id,
        initial_category_id=category_id,
    )


@catalog_admin_bp.route("/form/new")
@permission_required("edit_products")
def product_form_new():
    return render_template("catalog/partials/form.html", product=None, initial_category_id=None)


@catalog_admin_bp.route("/<int:product_id>/form")
@permission_required("edit_products")
@inject
def product_form_edit(product_id: int, facade: FromDishka[CatalogFacade]):
    product = facade.get_detail(product_id)
    return render_template("catalog/partials/form.html", product=product)


@catalog_admin_bp.route("/", methods=["POST"])
@permission_required("edit_products")
@inject
def create_product(facade: FromDishka[CatalogFacade]):
    title = request.form.get("title", "")
    price = safe_float(request.form.get("price", "0"), "price", min_val=0)
    description = request.form.get("description", "")
    images = [
        (file.filename or "img.jpg", file.read())
        for file in request.files.getlist("images")
    ]
    facade.create_product(title=title, price=price, description=description, images=images)
    params = parse_table_params(request.args)
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
@permission_required("edit_products")
@inject
def update_product(product_id: int, facade: FromDishka[CatalogFacade]):
    kwargs = {}
    if "title" in request.form:
        kwargs["title"] = request.form["title"]
    if "price" in request.form:
        kwargs["price"] = safe_float(request.form["price"], "price", min_val=0)
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
@permission_required("edit_products")
@inject
def delete_product(product_id: int, facade: FromDishka[CatalogFacade]):
    facade.delete_product(product_id)
    return "", 200


@taxonomy_admin_bp.route("/categories/")
@permission_required("view_category_tree")
def categories_page():
    return redirect("/admin/catalog/?view=tree")


@taxonomy_admin_bp.route("/tags/")
@permission_required("view_category_tree")
def tags_page():
    return redirect("/admin/catalog/?view=tags")


@taxonomy_admin_bp.route("/catalog/")
@any_permission_required("view_category_tree", "view_products", "edit_taxonomy")
def catalog_page():
    return render_template("catalog/pages/catalog.html")
