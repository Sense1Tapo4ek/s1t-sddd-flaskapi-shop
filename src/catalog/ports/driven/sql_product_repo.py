from dataclasses import dataclass
from typing import Any, ClassVar
from sqlalchemy import String, asc, cast, desc, func, select, text
from sqlalchemy.orm import aliased, selectinload

from shared.generics.errors import DrivenPortError
from shared.generics.pagination import PaginatedResult, PaginationParams
from shared.adapters.driven import SqlBaseRepo
from shared.helpers.db import handle_db_errors

from catalog.app.interfaces import IProductRepo
from catalog.domain import Product, ProductAttributeValue, Tag
from catalog.adapters.driven.db.models import (
    CategoryAttributeModel,
    CategoryModel,
    ProductAttributeValueModel,
    ProductImageModel,
    ProductModel,
    ProductTagModel,
    TagModel,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlProductRepo(SqlBaseRepo[Product, ProductModel], IProductRepo):

    _model_class: ClassVar[type[ProductModel]] = ProductModel

    def _to_domain(self, model: ProductModel) -> Product:
        category_path: list[str] = []
        current = model.category
        while current is not None:
            category_path.append(current.title)
            current = current.parent
        category_path.reverse()

        def attr_value(row: ProductAttributeValueModel) -> Any:
            attr_type = row.attribute.type
            if attr_type == "number":
                return row.value_number
            if attr_type == "boolean":
                return row.value_bool
            if attr_type == "multiselect":
                return row.value_json or []
            if attr_type in {"file", "image"} and row.attribute.value_mode == "multiple":
                return row.value_json or []
            if row.value_text is not None:
                return row.value_text
            return row.value_json

        return Product(
            id=model.id,
            title=model.title,
            price=model.price,
            description=model.description,
            is_active=model.is_active,
            created_at=model.created_at,
            images=[img.file_path for img in model.images],
            category_id=model.category_id,
            category_title=model.category.title if model.category else "",
            category_slug=model.category.slug if model.category else "",
            category_path=category_path,
            tags=[
                Tag(
                    id=tag.id,
                    title=tag.title,
                    slug=tag.slug,
                    color=tag.color,
                    sort_order=tag.sort_order,
                    is_active=tag.is_active,
                    created_at=tag.created_at,
                )
                for tag in model.tags
            ],
            attributes=[
                ProductAttributeValue(
                    attribute_id=row.attribute_id,
                    code=row.attribute.code,
                    title=row.attribute.title,
                    type=row.attribute.type,
                    value=attr_value(row),
                    unit=row.attribute.unit,
                )
                for row in model.attribute_values
            ],
        )

    def _load_options(self) -> list[Any]:
        return [
            selectinload(ProductModel.images),
            selectinload(ProductModel.tags),
            selectinload(ProductModel.category).selectinload(CategoryModel.parent),
            selectinload(ProductModel.attribute_values).selectinload(
                ProductAttributeValueModel.attribute
            ),
        ]

    def get_by_id(self, product_id: int) -> Product | None:
        with self._session_factory() as session:
            model = session.execute(
                select(ProductModel)
                .where(ProductModel.id == product_id)
                .options(*self._load_options())
            ).scalar_one_or_none()
            return self._to_domain(model) if model else None

    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Product]:
        with self._session_factory() as session:
            stmt = select(ProductModel).where(ProductModel.is_active)
            return self._paginate(
                session=session, stmt=stmt, params=params,
                default_sort="id",
                load_options=self._load_options(),
            )

    def get_random(self, limit: int) -> list[Product]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ProductModel)
                .where(ProductModel.is_active)
                .options(*self._load_options())
                .order_by(func.random())
                .limit(limit)
            ).scalars().all()
            return [self._to_domain(r) for r in rows]

    def search(self, query: str, params: PaginationParams) -> PaginatedResult[Product]:
        with self._session_factory() as session:
            stmt = select(ProductModel)
            if query:
                stmt = stmt.where(func.lower(ProductModel.title).contains(func.lower(query)))
            attribute_category_id = self._attribute_filter_category_id(params.filters)
            stmt, direct_filters = self._apply_taxonomy_filters(session, stmt, params.filters)
            stmt, sort_by = self._apply_catalog_sort(
                session, stmt, params.sort_by, params.sort_dir, attribute_category_id
            )
            safe_params = PaginationParams(
                page=params.page,
                limit=params.limit,
                sort_by=sort_by,
                sort_dir=params.sort_dir,
                filters=direct_filters,
            )
            return self._paginate(
                session=session, stmt=stmt, params=safe_params,
                default_sort="id",
                load_options=self._load_options(),
            )

    def _sort_expr(self, expression, sort_dir: str):
        return desc(expression) if sort_dir == "desc" else asc(expression)

    def _apply_catalog_sort(
        self,
        session,
        stmt,
        sort_by: str | None,
        sort_dir: str,
        attribute_category_id: int | None = None,
    ) -> tuple[Any, str | None]:
        if sort_by and sort_by.startswith("attr."):
            code = sort_by.removeprefix("attr.")
            _, sort_value = self._attribute_scalar_value(
                session, code, category_id=attribute_category_id
            )
            return (
                stmt.add_columns(sort_value.label("_attr_sort")).order_by(
                    self._sort_expr(sort_value, sort_dir)
                ),
                None,
            )

        if sort_by in {"category", "category_title", "category_path"}:
            category_paths = (
                select(
                    CategoryModel.id.label("id"),
                    CategoryModel.title.label("path"),
                )
                .where(CategoryModel.parent_id.is_(None))
                .cte("category_paths", recursive=True)
            )
            child = aliased(CategoryModel)
            category_paths = category_paths.union_all(
                select(
                    child.id,
                    (category_paths.c.path + " / " + child.title).label("path"),
                ).where(child.parent_id == category_paths.c.id)
            )
            category_path = (
                select(category_paths.c.path)
                .where(category_paths.c.id == ProductModel.category_id)
                .scalar_subquery()
            )
            sort_value = func.coalesce(category_path, "")
            return (
                stmt.add_columns(sort_value.label("_category_sort")).order_by(
                    self._sort_expr(sort_value, sort_dir)
                ),
                None,
            )

        if sort_by in {"tags", "tag"}:
            first_tag_title = (
                select(func.min(TagModel.title))
                .select_from(ProductTagModel)
                .join(TagModel, TagModel.id == ProductTagModel.tag_id)
                .where(ProductTagModel.product_id == ProductModel.id)
                .correlate(ProductModel)
                .scalar_subquery()
            )
            sort_value = func.coalesce(first_tag_title, "")
            return (
                stmt.add_columns(sort_value.label("_tag_sort")).order_by(
                    self._sort_expr(sort_value, sort_dir)
                ),
                None,
            )

        return stmt, sort_by

    def _descendant_ids(
        self, session, category_id: int, include_self: bool = True
    ) -> list[int]:
        rows = session.execute(select(CategoryModel.id, CategoryModel.parent_id)).all()
        children_by_parent: dict[int | None, list[int]] = {}
        for row_id, parent_id in rows:
            children_by_parent.setdefault(parent_id, []).append(row_id)
        result = [category_id] if include_self else []
        stack = list(children_by_parent.get(category_id, []))
        while stack:
            current = stack.pop()
            result.append(current)
            stack.extend(children_by_parent.get(current, []))
        return result

    def _attribute_filter_category_id(self, filters: dict[str, Any]) -> int | None:
        try:
            return int(filters.get("category_id"))
        except (TypeError, ValueError):
            return None

    def _category_chain_ids(self, session, category_id: int) -> list[int]:
        rows = session.execute(select(CategoryModel.id, CategoryModel.parent_id)).all()
        by_id = {row_id: parent_id for row_id, parent_id in rows}
        chain: list[int] = []
        current: int | None = category_id
        seen: set[int] = set()
        while current is not None and current not in seen and current in by_id:
            chain.append(current)
            seen.add(current)
            current = by_id[current]
        chain.reverse()
        return chain

    def _attribute_type_for_code(
        self, session, code: str, category_id: int | None = None
    ) -> str:
        if category_id is not None:
            chain_ids = self._category_chain_ids(session, category_id)
            if chain_ids:
                rows = session.execute(
                    select(CategoryAttributeModel.category_id, CategoryAttributeModel.type)
                    .where(
                        CategoryAttributeModel.code == code,
                        CategoryAttributeModel.category_id.in_(chain_ids),
                    )
                ).all()
                type_by_category = {
                    row_category_id: row_type for row_category_id, row_type in rows
                }
                for chain_id in reversed(chain_ids):
                    if chain_id in type_by_category:
                        return type_by_category[chain_id]
        return (
            session.scalar(
                select(CategoryAttributeModel.type)
                .where(CategoryAttributeModel.code == code)
                .limit(1)
            )
            or "text"
        )

    def _attribute_value_column(self, value_alias, attr_type: str):
        if attr_type == "number":
            return value_alias.value_number
        if attr_type == "boolean":
            return value_alias.value_bool
        if attr_type == "multiselect":
            return cast(value_alias.value_json, String)
        if attr_type in {"file", "image"}:
            return func.coalesce(
                value_alias.value_text,
                cast(value_alias.value_json, String),
            )
        return value_alias.value_text

    def _attribute_scalar_value(
        self, session, code: str, *, category_id: int | None = None
    ):
        attr_type = self._attribute_type_for_code(session, code, category_id)
        attr_alias = aliased(CategoryAttributeModel)
        value_alias = aliased(ProductAttributeValueModel)
        value_col = self._attribute_value_column(value_alias, attr_type)
        sort_value = (
            select(value_col)
            .select_from(value_alias)
            .join(attr_alias, value_alias.attribute_id == attr_alias.id)
            .where(value_alias.product_id == ProductModel.id, attr_alias.code == code)
            .limit(1)
            .correlate(ProductModel)
            .scalar_subquery()
        )
        if attr_type == "date":
            sort_value = func.coalesce(sort_value, func.date(ProductModel.created_at))
        return attr_type, sort_value

    def _apply_attr_filter(
        self,
        session,
        stmt,
        code: str,
        op: str,
        raw_value: str,
        *,
        category_id: int | None = None,
    ):
        attr_type, value_col = self._attribute_scalar_value(
            session, code, category_id=category_id
        )
        if attr_type == "number":
            try:
                raw_value = float(raw_value)
            except (TypeError, ValueError):
                raw_value = 0
        elif attr_type == "boolean":
            raw_value = str(raw_value).lower() in ("1", "true", "yes", "on", "да")

        if op == "eq":
            if attr_type in {"multiselect"}:
                return stmt.where(
                    func.lower(value_col).contains(func.lower(str(raw_value)))
                )
            return stmt.where(value_col == raw_value)
        if op == "ilike":
            return stmt.where(func.lower(value_col).contains(func.lower(str(raw_value))))
        if op == "gte":
            return stmt.where(value_col >= raw_value)
        if op == "lte":
            return stmt.where(value_col <= raw_value)
        return stmt

    def _apply_taxonomy_filters(self, session, stmt, filters: dict[str, Any]):
        direct_filters: dict[str, Any] = {}
        include_desc = str(filters.get("include_descendants", "")).lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        for key, value in filters.items():
            if value in ("", None) or key == "include_descendants":
                continue

            if key == "category_id":
                try:
                    category_id = int(value)
                except (TypeError, ValueError):
                    stmt = stmt.where(ProductModel.id == -1)
                    continue
                ids = (
                    self._descendant_ids(session, category_id)
                    if include_desc
                    else [category_id]
                )
                stmt = stmt.where(ProductModel.category_id.in_(ids))
                continue

            if key == "category":
                category = session.execute(
                    select(CategoryModel).where(CategoryModel.slug == str(value))
                ).scalar_one_or_none()
                if category:
                    ids = (
                        self._descendant_ids(session, category.id)
                        if include_desc
                        else [category.id]
                    )
                    stmt = stmt.where(ProductModel.category_id.in_(ids))
                else:
                    stmt = stmt.where(ProductModel.id == -1)
                continue

            if key == "tags":
                slugs = [slug.strip() for slug in str(value).split(",") if slug.strip()]
                if slugs:
                    stmt = stmt.join(ProductModel.tags).where(TagModel.slug.in_(slugs))
                continue

            if key.startswith("attr."):
                raw = key.removeprefix("attr.")
                code, op = raw.split("__", 1) if "__" in raw else (raw, "eq")
                stmt = self._apply_attr_filter(
                    session,
                    stmt,
                    code,
                    op,
                    value,
                    category_id=self._attribute_filter_category_id(filters),
                )
                continue

            direct_filters[key] = value

        return stmt.distinct(), direct_filters

    def _sync_product_relations(self, session, model: ProductModel, product: Product) -> None:
        if product.category_id is not None:
            model.category_id = product.category_id

        if product.tags is not None:
            tag_ids = [tag.id for tag in product.tags if tag.id]
            model.tags = (
                session.execute(select(TagModel).where(TagModel.id.in_(tag_ids))).scalars().all()
                if tag_ids
                else []
            )

        session.query(ProductAttributeValueModel).filter(
            ProductAttributeValueModel.product_id == model.id
        ).delete()
        for attr in product.attributes:
            row = ProductAttributeValueModel(
                product_id=model.id,
                attribute_id=attr.attribute_id,
            )
            if attr.type == "number":
                row.value_number = float(attr.value) if attr.value not in ("", None) else None
            elif attr.type == "boolean":
                row.value_bool = bool(attr.value)
            elif attr.type == "multiselect":
                row.value_json = attr.value if isinstance(attr.value, list) else [attr.value]
            elif attr.type in {"file", "image"} and isinstance(attr.value, list):
                row.value_json = attr.value
            else:
                row.value_text = "" if attr.value is None else str(attr.value)
            session.add(row)

    @handle_db_errors("create product")
    def create(self, product: Product) -> Product:
        with self._session_factory() as session:
            model = ProductModel(
                category_id=product.category_id,
                title=product.title, price=product.price,
                description=product.description, is_active=product.is_active,
            )
            session.add(model)
            session.flush()
            for path in product.images:
                session.add(ProductImageModel(product_id=model.id, file_path=path))
            self._sync_product_relations(session, model, product)
            session.commit()
            session.refresh(model)
            model = session.execute(
                select(ProductModel)
                .where(ProductModel.id == model.id)
                .options(*self._load_options())
            ).scalar_one()
            return self._to_domain(model)

    @handle_db_errors("update product")
    def update(self, product: Product) -> Product:
        with self._session_factory() as session:
            model = session.get(ProductModel, product.id)
            if not model:
                raise DrivenPortError(f"Product {product.id} missing during update")
            model.title = product.title
            model.price = product.price
            model.description = product.description
            model.category_id = product.category_id
            session.query(ProductImageModel).filter(
                ProductImageModel.product_id == model.id
            ).delete()
            for path in product.images:
                session.add(ProductImageModel(product_id=model.id, file_path=path))
            self._sync_product_relations(session, model, product)
            session.commit()
            session.refresh(model)
            model = session.execute(
                select(ProductModel)
                .where(ProductModel.id == model.id)
                .options(*self._load_options())
            ).scalar_one()
            return self._to_domain(model)

    @handle_db_errors("delete product")
    def delete(self, product_id: int) -> bool:
        with self._session_factory() as session:
            model = session.get(ProductModel, product_id)
            if model:
                session.delete(model)
                session.commit()
                return True
            return False

    @handle_db_errors("swap ids")
    def swap_ids(self, id_a: int, id_b: int) -> None:
        with self._session_factory() as session:
            if id_a == id_b:
                return

            model_a = session.get(ProductModel, id_a)
            model_b = session.get(ProductModel, id_b)
            if model_a is None or model_b is None:
                raise DrivenPortError("Cannot swap missing products")

            temp = -1
            while session.get(ProductModel, temp) is not None:
                temp -= 1
            temp_model = ProductModel(
                id=temp,
                category_id=None,
                title="__swap_temp__",
                price=0,
                description="",
                is_active=False,
            )
            session.add(temp_model)
            session.flush()

            scalar_fields = (
                "category_id",
                "title",
                "price",
                "description",
                "is_active",
                "created_at",
            )
            values_a = {field: getattr(model_a, field) for field in scalar_fields}
            values_b = {field: getattr(model_b, field) for field in scalar_fields}
            for field, value in values_b.items():
                setattr(model_a, field, value)
            for field, value in values_a.items():
                setattr(model_b, field, value)

            fk_tables = (
                "product_images",
                "product_tags",
                "product_attribute_values",
            )
            for table in fk_tables:
                session.execute(
                    text(f"UPDATE {table} SET product_id = :t WHERE product_id = :a"),
                    {"t": temp, "a": id_a},
                )
            for table in fk_tables:
                session.execute(
                    text(f"UPDATE {table} SET product_id = :a WHERE product_id = :b"),
                    {"a": id_a, "b": id_b},
                )
            for table in fk_tables:
                session.execute(
                    text(f"UPDATE {table} SET product_id = :b WHERE product_id = :t"),
                    {"b": id_b, "t": temp},
                )
            session.delete(temp_model)
            session.commit()
