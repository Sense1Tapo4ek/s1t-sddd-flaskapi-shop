import json

from apiflask import APIBlueprint
from dishka.integrations.flask import inject, FromDishka
from flask import request

from shared.adapters.driving.middleware import any_permission_required, permission_required
from shared.generics.errors import DrivingPortError
from shared.helpers.parsing import parse_optional_int, safe_float, safe_int
from shared.ports.driving.schemas import SuccessResponse
from catalog.ports.driving import (
    AdminProductListOut,
    CatalogFacade,
    CatalogListOut,
    CatalogQuery,
    CategoryAttributeCreateIn,
    CategoryAttributeUpdateIn,
    CategoryCreateIn,
    CategoryMoveIn,
    CategoryUpdateIn,
    RandomQuery,
    DeleteImageIn,
    ProductDetailOut,
    ProductSearchQuery,
    SwapSortOrderIn,
    TagCreateIn,
    TagUpdateIn,
)

catalog_bp = APIBlueprint("catalog", __name__, url_prefix="/catalog")


# --- PUBLIC ---


def _taxonomy_payload_from_form(*, include_missing: bool) -> dict:
    payload: dict = {}
    if include_missing or "category_id" in request.form:
        payload["category_id"] = parse_optional_int(
            request.form.get("category_id", ""),
            "category_id",
        )

    if include_missing or "tag_ids" in request.form:
        payload["tag_ids"] = _tag_ids_from_form()

    has_attr_fields = "attribute_values" in request.form or any(
        key.startswith("attr.") for key in request.form
    )
    if include_missing or has_attr_fields:
        payload["attribute_values"] = _attribute_values_from_form()

    return payload


def _tag_ids_from_form() -> list[int]:
    tag_ids: list[int] = []
    for raw in request.form.getlist("tag_ids"):
        if not raw:
            continue
        for part in str(raw).split(","):
            if not part.strip():
                continue
            tag_id = parse_optional_int(part.strip(), "tag_ids")
            if tag_id is not None:
                tag_ids.append(tag_id)
    return tag_ids


def _attribute_values_from_form() -> dict:
    raw_attrs = request.form.get("attribute_values", "")
    try:
        attribute_values = json.loads(raw_attrs) if raw_attrs else {}
    except json.JSONDecodeError:
        raise DrivingPortError("Invalid attribute_values JSON")
    if not isinstance(attribute_values, dict):
        raise DrivingPortError("attribute_values must be an object")
    for key, value in request.form.items():
        if key.startswith("attr."):
            attribute_values[key.removeprefix("attr.")] = value
    return attribute_values


def _catalog_filters_from_args(reserved: set[str]) -> dict[str, str]:
    filters = {
        key: value
        for key, value in request.args.to_dict().items()
        if key not in reserved and value != "" and key != "is_active"
    }
    if "category_id" in filters:
        filters["category_id"] = str(parse_optional_int(filters["category_id"], "category_id"))
    return filters


@catalog_bp.get("")
@catalog_bp.input(CatalogQuery, location="query")
@catalog_bp.output(CatalogListOut)
@catalog_bp.doc(
    summary="Get product list (Public)",
    description="Returns a paginated list of active products.",
)
@inject
def get_catalog(query_data: CatalogQuery, facade: FromDishka[CatalogFacade]):
    filters = _catalog_filters_from_args({"page", "limit"})
    res = facade.get_public_catalog(
        page=query_data.page,
        limit=query_data.limit,
        filters=filters,
    )
    return res.model_dump()


@catalog_bp.get("/categories/tree")
@catalog_bp.doc(
    summary="Get category tree (Public)",
    description="Returns active categories as a nested tree.",
)
@inject
def get_category_tree(facade: FromDishka[CatalogFacade]):
    return [category.model_dump() for category in facade.list_public_category_tree()]


@catalog_bp.get("/tags")
@catalog_bp.doc(
    summary="Get tags (Public)",
    description="Returns active catalog tags.",
)
@inject
def get_tags(facade: FromDishka[CatalogFacade]):
    return [tag.model_dump() for tag in facade.list_public_tags()]


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
    res = facade.get_detail(product_id)
    return res.model_dump()


# --- ADMIN (Protected) ---


@catalog_bp.get("/admin/search")
@permission_required("view_products")
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
@permission_required("view_products")
@catalog_bp.doc(
    summary="Filter schema for smart table (ADMIN ONLY)",
    description="Returns available field configs for building dynamic filters on the frontend.",
    security="JWTAuth",
)
@inject
def admin_search_schema(facade: FromDishka[CatalogFacade]):
    def walk_category_options(categories, prefix=""):
        result = []
        for category in categories:
            label = f"{prefix}{category.title}"
            result.append({"value": str(category.id), "label": label})
            result.extend(walk_category_options(category.children, prefix=f"{label} / "))
        return result

    def attribute_field(attribute):
        key = f"attr.{attribute.code}"
        if attribute.type == "number":
            return {
                "key": key,
                "label": attribute.title,
                "type": "number",
                "operators": ["eq", "gte", "lte"],
            }
        if attribute.type == "date":
            return {
                "key": key,
                "label": attribute.title,
                "type": "date",
                "operators": ["eq", "gte", "lte"],
            }
        if attribute.type == "boolean":
            return {
                "key": key,
                "label": attribute.title,
                "type": "enum",
                "operators": ["eq"],
                "options": [
                    {"value": "true", "label": "Да"},
                    {"value": "false", "label": "Нет"},
                ],
            }
        if attribute.type in {"select", "multiselect"}:
            return {
                "key": key,
                "label": attribute.title,
                "type": "enum",
                "operators": ["eq"],
                "options": [
                    {"value": option.value, "label": option.label}
                    for option in attribute.options
                ],
            }
        return {
            "key": key,
            "label": attribute.title,
            "type": "string",
            "operators": ["ilike", "eq"],
        }

    categories = facade.list_category_tree(include_inactive=True)
    tags = facade.list_tags(include_inactive=True)
    category_id = safe_int(request.args.get("category_id", 0), default=0)
    attribute_fields = []
    if category_id > 0:
        attributes = facade.get_category_attributes(category_id).items
        attribute_fields = [attribute_field(attribute) for attribute in attributes]
    return {
        "fields": [
            {"key": "id",         "label": "ID",       "type": "number", "operators": ["eq"]},
            {"key": "title",      "label": "Название", "type": "string", "operators": ["ilike", "eq"]},
            {"key": "price",      "label": "Цена",     "type": "number", "operators": ["eq", "gte", "lte"]},
            {"key": "created_at", "label": "Дата",     "type": "date",   "operators": ["eq", "gte", "lte"]},
            {
                "key": "category_id",
                "label": "Категория",
                "type": "enum",
                "operators": ["eq"],
                "options": walk_category_options(categories),
            },
            {
                "key": "tags",
                "label": "Теги",
                "type": "enum",
                "operators": ["eq"],
                "options": [
                    {"value": tag.slug, "label": tag.title}
                    for tag in tags
                ],
            },
        ] + attribute_fields
    }


@catalog_bp.post("")
@permission_required("edit_products")
@catalog_bp.output(ProductDetailOut, status_code=201)
@catalog_bp.doc(
    summary="Create product (ADMIN ONLY)",
    description="Creates a new product. Supports multipart/form-data image upload.",
    security="JWTAuth",
)
@inject
def admin_create(facade: FromDishka[CatalogFacade]):
    title = request.form.get("title", "")
    price = safe_float(request.form.get("price", "0"), "price", min_val=0)
    description = request.form.get("description", "")
    images = [
        (file.filename or "img.jpg", file.read())
        for file in request.files.getlist("images")
    ]

    res = facade.create_product(
        title=title,
        price=price,
        description=description,
        images=images,
        **_taxonomy_payload_from_form(include_missing=True),
    )
    return res.model_dump(), 201


@catalog_bp.get("/admin/products/<int:product_id>")
@permission_required("view_products")
@catalog_bp.output(ProductDetailOut)
@catalog_bp.doc(
    summary="Product detail (ADMIN ONLY)",
    description="Returns product information for admin editing, including inactive products.",
    security="JWTAuth",
)
@inject
def admin_get_product(product_id: int, facade: FromDishka[CatalogFacade]):
    res = facade.get_admin_detail(product_id)
    return res.model_dump()


@catalog_bp.put("/<int:product_id>")
@permission_required("edit_products")
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
    kwargs.update(_taxonomy_payload_from_form(include_missing=False))

    res = facade.update_product(product_id, **kwargs)
    return res.model_dump()


@catalog_bp.delete("/<int:product_id>")
@permission_required("edit_products")
@catalog_bp.output(SuccessResponse)
@catalog_bp.doc(
    summary="Delete product (ADMIN ONLY)",
    description="Permanently deletes a product and all associated images.",
    security="JWTAuth",
)
@inject
def admin_delete(product_id: int, facade: FromDishka[CatalogFacade]):
    facade.delete_product(product_id)
    return {"success": True}


@catalog_bp.delete("/<int:product_id>/images")
@permission_required("edit_products")
@catalog_bp.input(DeleteImageIn)
@catalog_bp.output(ProductDetailOut)
@catalog_bp.doc(
    summary="Delete product image (ADMIN ONLY)",
    description="Deletes a specific product image by path.",
    security="JWTAuth",
)
@inject
def admin_delete_image(product_id: int, json_data: DeleteImageIn, facade: FromDishka[CatalogFacade]):
    res = facade.delete_image(product_id, json_data.image_path)
    return res.model_dump()


@catalog_bp.post("/admin/swap")
@permission_required("edit_products")
@catalog_bp.input(SwapSortOrderIn)
@catalog_bp.output(SuccessResponse)
@catalog_bp.doc(summary="Swap sort order of two products (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_swap(json_data: SwapSortOrderIn, facade: FromDishka[CatalogFacade]):
    facade.swap_ids(json_data.id_a, json_data.id_b)
    return {"success": True}


@catalog_bp.post("/admin/demo-data")
@permission_required("create_demo_data")
@catalog_bp.doc(summary="Create demo catalog data (SUPERADMIN ONLY)", security="JWTAuth")
@inject
def admin_create_demo_data(facade: FromDishka[CatalogFacade]):
    return facade.create_demo_data()


@catalog_bp.get("/admin/categories/tree")
@permission_required("view_category_tree")
@catalog_bp.doc(summary="Category tree (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_category_tree(facade: FromDishka[CatalogFacade]):
    return [
        category.model_dump()
        for category in facade.list_category_tree(include_inactive=True)
    ]


@catalog_bp.get("/admin/categories/<int:category_id>")
@permission_required("view_category_tree")
@catalog_bp.doc(summary="Category detail (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_get_category(category_id: int, facade: FromDishka[CatalogFacade]):
    return facade.get_category(category_id).model_dump()


@catalog_bp.post("/admin/categories")
@permission_required("edit_taxonomy")
@catalog_bp.input(CategoryCreateIn)
@catalog_bp.doc(summary="Create category (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_create_category(json_data: CategoryCreateIn, facade: FromDishka[CatalogFacade]):
    return facade.create_category(json_data).model_dump(), 201


@catalog_bp.put("/admin/categories/<int:category_id>")
@permission_required("edit_taxonomy")
@catalog_bp.input(CategoryUpdateIn)
@catalog_bp.doc(summary="Update category (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_update_category(
    category_id: int,
    json_data: CategoryUpdateIn,
    facade: FromDishka[CatalogFacade],
):
    return facade.update_category(category_id, json_data).model_dump()


@catalog_bp.post("/admin/categories/<int:category_id>/move")
@permission_required("edit_taxonomy")
@catalog_bp.input(CategoryMoveIn)
@catalog_bp.doc(summary="Move category (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_move_category(
    category_id: int,
    json_data: CategoryMoveIn,
    facade: FromDishka[CatalogFacade],
):
    return facade.move_category(category_id, json_data).model_dump()


@catalog_bp.delete("/admin/categories/<int:category_id>")
@permission_required("edit_taxonomy")
@catalog_bp.output(SuccessResponse)
@catalog_bp.doc(summary="Delete category (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_delete_category(category_id: int, facade: FromDishka[CatalogFacade]):
    facade.delete_category(category_id)
    return {"success": True}


@catalog_bp.get("/admin/categories/<int:category_id>/products")
@permission_required("view_products")
@catalog_bp.doc(summary="Products by category (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_category_products(category_id: int, facade: FromDishka[CatalogFacade]):
    filters = _catalog_filters_from_args(
        {"q", "page", "limit", "sort_by", "sort_dir", "include_descendants"}
    )
    result = facade.get_category_products(
        category_id,
        include_descendants=request.args.get("include_descendants") in ("1", "true", "on"),
        query=request.args.get("q", ""),
        page=safe_int(request.args.get("page", 1), default=1),
        limit=safe_int(request.args.get("limit", 20), default=20),
        sort_by=request.args.get("sort_by"),
        sort_dir=request.args.get("sort_dir", "asc"),
        filters=filters,
    )
    return result.model_dump()


@catalog_bp.get("/admin/categories/<int:category_id>/attributes")
@permission_required("view_category_tree")
@catalog_bp.doc(summary="Effective category attributes (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_category_attributes(category_id: int, facade: FromDishka[CatalogFacade]):
    return facade.get_category_attributes(category_id).model_dump()


@catalog_bp.post("/admin/categories/<int:category_id>/attributes")
@permission_required("edit_taxonomy")
@catalog_bp.input(CategoryAttributeCreateIn)
@catalog_bp.doc(summary="Create category attribute (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_create_category_attribute(
    category_id: int,
    json_data: CategoryAttributeCreateIn,
    facade: FromDishka[CatalogFacade],
):
    return facade.create_category_attribute(category_id, json_data).model_dump(), 201


@catalog_bp.put("/admin/categories/<int:category_id>/attributes/<int:attribute_id>")
@permission_required("edit_taxonomy")
@catalog_bp.input(CategoryAttributeUpdateIn)
@catalog_bp.doc(summary="Update category attribute (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_update_category_attribute(
    category_id: int,
    attribute_id: int,
    json_data: CategoryAttributeUpdateIn,
    facade: FromDishka[CatalogFacade],
):
    del category_id
    return facade.update_category_attribute(attribute_id, json_data).model_dump()


@catalog_bp.delete("/admin/categories/<int:category_id>/attributes/<int:attribute_id>")
@permission_required("edit_taxonomy")
@catalog_bp.output(SuccessResponse)
@catalog_bp.doc(summary="Delete category attribute (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_delete_category_attribute(
    category_id: int,
    attribute_id: int,
    facade: FromDishka[CatalogFacade],
):
    del category_id
    facade.delete_category_attribute(attribute_id)
    return {"success": True}


@catalog_bp.get("/admin/tags")
@permission_required("view_category_tree")
@catalog_bp.doc(summary="List tags (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_list_tags(facade: FromDishka[CatalogFacade]):
    tags = facade.list_tags(include_inactive=True)
    rows = [tag.model_dump() for tag in tags]
    raw = request.args.to_dict()
    for key, value in raw.items():
        if key in {"page", "limit", "sort_by", "sort_dir"} or value == "":
            continue
        field, op = key.split("__", 1) if "__" in key else (key, "eq")
        if field not in {"id", "title", "slug", "is_active"}:
            continue
        if op == "ilike":
            rows = [row for row in rows if value.lower() in str(row.get(field, "")).lower()]
        else:
            rows = [row for row in rows if str(row.get(field, "")).lower() == value.lower()]
    sort_by = raw.get("sort_by") or "sort_order"
    sort_dir = raw.get("sort_dir", "asc")
    if sort_by in {"id", "title", "slug", "sort_order", "is_active"}:
        rows.sort(
            key=lambda row: row.get(sort_by) if row.get(sort_by) is not None else "",
            reverse=sort_dir == "desc",
        )
    total = len(rows)
    page = safe_int(raw.get("page", 1), default=1)
    limit = safe_int(raw.get("limit", 20), default=20)
    start = (page - 1) * limit
    return {"items": rows[start:start + limit], "total": total}


@catalog_bp.get("/admin/tags/search/schema")
@permission_required("view_category_tree")
@catalog_bp.doc(summary="Tag filter schema (ADMIN ONLY)", security="JWTAuth")
def admin_tags_schema():
    return {
        "fields": [
            {"key": "id", "label": "ID", "type": "number", "operators": ["eq"]},
            {"key": "title", "label": "Название", "type": "string", "operators": ["ilike", "eq"]},
            {"key": "slug", "label": "Slug", "type": "string", "operators": ["ilike", "eq"]},
            {
                "key": "is_active",
                "label": "Активен",
                "type": "enum",
                "operators": ["eq"],
                "options": [
                    {"value": "true", "label": "Да"},
                    {"value": "false", "label": "Нет"},
                ],
            },
        ]
    }


@catalog_bp.post("/admin/tags")
@permission_required("edit_taxonomy")
@catalog_bp.input(TagCreateIn)
@catalog_bp.doc(summary="Create tag (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_create_tag(json_data: TagCreateIn, facade: FromDishka[CatalogFacade]):
    return facade.create_tag(json_data).model_dump(), 201


@catalog_bp.put("/admin/tags/<int:tag_id>")
@permission_required("edit_taxonomy")
@catalog_bp.input(TagUpdateIn)
@catalog_bp.doc(summary="Update tag (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_update_tag(tag_id: int, json_data: TagUpdateIn, facade: FromDishka[CatalogFacade]):
    return facade.update_tag(tag_id, json_data).model_dump()


@catalog_bp.delete("/admin/tags/<int:tag_id>")
@permission_required("edit_taxonomy")
@catalog_bp.output(SuccessResponse)
@catalog_bp.doc(summary="Delete tag (ADMIN ONLY)", security="JWTAuth")
@inject
def admin_delete_tag(tag_id: int, facade: FromDishka[CatalogFacade]):
    facade.delete_tag(tag_id)
    return {"success": True}
