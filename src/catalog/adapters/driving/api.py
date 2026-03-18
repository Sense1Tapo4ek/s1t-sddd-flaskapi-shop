from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka
from flask import request

from shared.adapters.driving.middleware import jwt_required
from shared.ports.driving.schemas import SuccessResponse
from catalog.ports.driving import (
    CatalogFacade,
    ProductSearchQuery,
    ProductDetailOut,
    CatalogListOut,
    AdminProductListOut,
    CatalogQuery,
    RandomQuery,
    DeleteImageIn,
)
from catalog.domain import ProductNotFoundError

catalog_bp = APIBlueprint("catalog", __name__, url_prefix="/catalog")


# --- PUBLIC ---


@catalog_bp.get("")
@catalog_bp.input(CatalogQuery, location="query")
@catalog_bp.output(CatalogListOut)
@catalog_bp.doc(
    summary="Get product list (Public)",
    description="Returns a paginated list of active products.",
)
@inject
def get_catalog(query_data: CatalogQuery, facade: FromDishka[CatalogFacade]):
    res = facade.get_public_catalog(page=query_data.page, limit=query_data.limit)
    return res.model_dump()


@catalog_bp.get("/random")
@catalog_bp.input(RandomQuery, location="query")
@catalog_bp.doc(
    summary="Get random products (Public)",
    description="Returns a given number of random active products.",
)
@inject
def get_random(query_data: RandomQuery, facade: FromDishka[CatalogFacade]):
    res = facade.get_random(limit=query_data.limit)
    return [p.model_dump() for p in res]


@catalog_bp.get("/<int:product_id>")
@catalog_bp.output(ProductDetailOut)
@catalog_bp.doc(
    summary="Product detail (Public)",
    description="Returns full information about a product by ID, including all uploaded images.",
)
@inject
def get_detail(product_id: int, facade: FromDishka[CatalogFacade]):
    try:
        res = facade.get_detail(product_id)
        return res.model_dump()
    except ProductNotFoundError:
        return {"error": "Product not found"}, 404


# --- ADMIN (Protected) ---


@catalog_bp.get("/admin/search")
@jwt_required
@catalog_bp.input(ProductSearchQuery, location="query")
@catalog_bp.output(AdminProductListOut)
@catalog_bp.doc(
    summary="Search and filter products (ADMIN ONLY)",
    description="Advanced catalog search with dynamic filters, sorting and pagination.",
    security="JWTAuth",
)
@inject
def admin_search(query_data: ProductSearchQuery, facade: FromDishka[CatalogFacade]):
    raw_query_dict = request.args.to_dict()
    reserved_keys = {"q", "page", "limit", "sort_by", "sort_dir"}

    filters = {
        k: v for k, v in raw_query_dict.items() if k not in reserved_keys and v != ""
    }

    res = facade.search_products(
        query=query_data.q,
        page=query_data.page,
        limit=query_data.limit,
        sort_by=query_data.sort_by,
        sort_dir=query_data.sort_dir,
        filters=filters,
    )
    return res.model_dump()


@catalog_bp.get("/admin/search/schema")
@jwt_required
@catalog_bp.doc(
    summary="Filter schema for smart table (ADMIN ONLY)",
    description="Returns available field configs for building dynamic filters on the frontend.",
    security="JWTAuth",
)
@inject
def admin_search_schema(facade: FromDishka[CatalogFacade]):
    return {
        "fields": [
            {"key": "id",         "label": "ID",       "type": "number", "operators": ["eq"]},
            {"key": "title",      "label": "Название", "type": "string", "operators": ["ilike", "eq"]},
            {"key": "price",      "label": "Цена",     "type": "number", "operators": ["eq", "gte", "lte"]},
            {"key": "created_at", "label": "Дата",     "type": "date",   "operators": ["eq", "gte", "lte"]},
        ]
    }


@catalog_bp.post("")
@jwt_required
@catalog_bp.output(ProductDetailOut, status_code=201)
@catalog_bp.doc(
    summary="Create product (ADMIN ONLY)",
    description="Creates a new product. Supports multipart/form-data image upload.",
    security="JWTAuth",
)
@inject
def admin_create(facade: FromDishka[CatalogFacade]):
    title = request.form.get("title", "")
    price = float(request.form.get("price", 0))
    description = request.form.get("description", "")
    images = [
        (file.filename or "img.jpg", file.read())
        for file in request.files.getlist("images")
    ]

    res = facade.create_product(
        title=title, price=price, description=description, images=images
    )
    return res.model_dump(), 201


@catalog_bp.put("/<int:product_id>")
@jwt_required
@catalog_bp.output(ProductDetailOut)
@catalog_bp.doc(
    summary="Update product (ADMIN ONLY)",
    description="Updates product fields. Supports adding new images and deleting old ones.",
    security="JWTAuth",
)
@inject
def admin_update(product_id: int, facade: FromDishka[CatalogFacade]):
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

    try:
        res = facade.update_product(product_id, **kwargs)
        return res.model_dump()
    except ProductNotFoundError:
        return {"error": "Product not found"}, 404


@catalog_bp.delete("/<int:product_id>")
@jwt_required
@catalog_bp.output(SuccessResponse)
@catalog_bp.doc(
    summary="Delete product (ADMIN ONLY)",
    description="Permanently deletes a product and all associated images.",
    security="JWTAuth",
)
@inject
def admin_delete(product_id: int, facade: FromDishka[CatalogFacade]):
    try:
        facade.delete_product(product_id)
        return {"success": True}
    except ProductNotFoundError:
        return {"error": "Product not found"}, 404


@catalog_bp.delete("/<int:product_id>/images")
@jwt_required
@catalog_bp.input(DeleteImageIn)
@catalog_bp.output(ProductDetailOut)
@catalog_bp.doc(
    summary="Delete product image (ADMIN ONLY)",
    description="Deletes a specific product image by path.",
    security="JWTAuth",
)
@inject
def admin_delete_image(product_id: int, json_data: DeleteImageIn, facade: FromDishka[CatalogFacade]):
    try:
        res = facade.delete_image(product_id, json_data.image_path)
        return res.model_dump()
    except ProductNotFoundError:
        return {"error": "Product not found"}, 404
