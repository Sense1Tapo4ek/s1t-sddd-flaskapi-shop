from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from catalog.app.interfaces import ITaxonomyRepo
from catalog.adapters.driven.db.models import (
    AttributeOptionModel,
    CategoryAttributeModel,
    CategoryModel,
    ProductModel,
    TagModel,
)
from catalog.domain import AttributeOption, Category, CategoryAttribute, Tag
from shared.helpers.db import handle_db_errors


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlTaxonomyRepo(ITaxonomyRepo):
    _session_factory: Callable[[], Session]

    def _to_category(self, model: CategoryModel, product_count: int = 0) -> Category:
        return Category(
            id=model.id,
            parent_id=model.parent_id,
            title=model.title,
            slug=model.slug,
            description=model.description or "",
            sort_order=model.sort_order or 0,
            is_active=model.is_active,
            created_at=model.created_at,
            product_count=product_count,
        )

    def _to_tag(self, model: TagModel, product_count: int = 0) -> Tag:
        return Tag(
            id=model.id,
            title=model.title,
            slug=model.slug,
            color=model.color or "#7c8c6e",
            sort_order=model.sort_order or 0,
            is_active=model.is_active,
            created_at=model.created_at,
            product_count=product_count,
        )

    def _to_option(self, model: AttributeOptionModel) -> AttributeOption:
        return AttributeOption(
            id=model.id,
            attribute_id=model.attribute_id,
            value=model.value,
            label=model.label,
            sort_order=model.sort_order or 0,
        )

    def _to_attribute(
        self,
        model: CategoryAttributeModel,
        *,
        inherited_from_id: int | None = None,
        inherited_from_title: str | None = None,
    ) -> CategoryAttribute:
        return CategoryAttribute(
            id=model.id,
            category_id=model.category_id,
            code=model.code,
            title=model.title,
            type=model.type,
            unit=model.unit,
            is_required=model.is_required,
            is_filterable=model.is_filterable,
            is_public=model.is_public,
            sort_order=model.sort_order or 0,
            value_mode=model.value_mode or "single",
            inherited_from_id=inherited_from_id,
            inherited_from_title=inherited_from_title,
            options=[self._to_option(option) for option in model.options],
        )

    @handle_db_errors("list categories")
    def list_categories(self, *, include_inactive: bool = True) -> list[Category]:
        with self._session_factory() as session:
            stmt = select(CategoryModel).order_by(CategoryModel.sort_order, CategoryModel.title)
            if not include_inactive:
                stmt = stmt.where(CategoryModel.is_active)
            models = session.execute(stmt).scalars().all()
            count_stmt = (
                select(ProductModel.category_id, func.count(ProductModel.id))
                .where(ProductModel.category_id.is_not(None))
                .group_by(ProductModel.category_id)
            )
            if not include_inactive:
                count_stmt = count_stmt.where(ProductModel.is_active)
            counts = dict(
                session.execute(count_stmt).all()
            )
            return [self._to_category(model, counts.get(model.id, 0)) for model in models]

    @handle_db_errors("get category")
    def get_category(self, category_id: int) -> Category | None:
        with self._session_factory() as session:
            model = session.get(CategoryModel, category_id)
            return self._to_category(model) if model else None

    @handle_db_errors("get category by slug")
    def get_category_by_slug(self, slug: str) -> Category | None:
        with self._session_factory() as session:
            model = session.execute(
                select(CategoryModel).where(CategoryModel.slug == slug)
            ).scalar_one_or_none()
            return self._to_category(model) if model else None

    @handle_db_errors("create category")
    def create_category(
        self,
        *,
        parent_id: int | None,
        title: str,
        slug: str,
        description: str,
        sort_order: int,
        is_active: bool,
    ) -> Category:
        with self._session_factory() as session:
            model = CategoryModel(
                parent_id=parent_id,
                title=title,
                slug=slug,
                description=description,
                sort_order=sort_order,
                is_active=is_active,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._to_category(model)

    @handle_db_errors("update category")
    def update_category(self, category_id: int, **kwargs: Any) -> Category:
        with self._session_factory() as session:
            model = session.get(CategoryModel, category_id)
            if model is None:
                raise LookupError(category_id)
            for field in ("parent_id", "title", "slug", "description", "sort_order", "is_active"):
                if field in kwargs:
                    setattr(model, field, kwargs[field])
            session.commit()
            session.refresh(model)
            return self._to_category(model)

    @handle_db_errors("delete category")
    def delete_category(self, category_id: int) -> None:
        with self._session_factory() as session:
            model = session.get(CategoryModel, category_id)
            if model is None:
                raise LookupError(category_id)
            session.delete(model)
            session.commit()

    @handle_db_errors("category has children")
    def category_has_children(self, category_id: int) -> bool:
        with self._session_factory() as session:
            return bool(
                session.scalar(
                    select(func.count(CategoryModel.id)).where(
                        CategoryModel.parent_id == category_id
                    )
                )
            )

    @handle_db_errors("category has products")
    def category_has_products(self, category_id: int) -> bool:
        with self._session_factory() as session:
            return bool(
                session.scalar(
                    select(func.count(ProductModel.id)).where(
                        ProductModel.category_id == category_id
                    )
                )
            )

    def is_leaf_category(self, category_id: int) -> bool:
        return not self.category_has_children(category_id)

    @handle_db_errors("descendant category ids")
    def descendant_ids(self, category_id: int, *, include_self: bool = True) -> list[int]:
        with self._session_factory() as session:
            rows = session.execute(select(CategoryModel.id, CategoryModel.parent_id)).all()
        children_by_parent: dict[int | None, list[int]] = {}
        for row_id, parent_id in rows:
            children_by_parent.setdefault(parent_id, []).append(row_id)
        result: list[int] = [category_id] if include_self else []
        stack = list(children_by_parent.get(category_id, []))
        while stack:
            current = stack.pop()
            result.append(current)
            stack.extend(children_by_parent.get(current, []))
        return result

    @handle_db_errors("list tags")
    def list_tags(self, *, include_inactive: bool = True) -> list[Tag]:
        with self._session_factory() as session:
            stmt = select(TagModel).order_by(TagModel.sort_order, TagModel.title)
            if not include_inactive:
                stmt = stmt.where(TagModel.is_active)
            models = session.execute(stmt).scalars().all()
            count_stmt = (
                select(TagModel.id, func.count(ProductModel.id))
                .join(TagModel.products, isouter=True)
                .group_by(TagModel.id)
            )
            if not include_inactive:
                count_stmt = count_stmt.where(
                    or_(ProductModel.id.is_(None), ProductModel.is_active.is_(True))
                )
            counts = dict(session.execute(count_stmt).all())
            return [self._to_tag(model, counts.get(model.id, 0)) for model in models]

    @handle_db_errors("get tag")
    def get_tag(self, tag_id: int) -> Tag | None:
        with self._session_factory() as session:
            model = session.get(TagModel, tag_id)
            return self._to_tag(model) if model else None

    @handle_db_errors("create tag")
    def create_tag(
        self,
        *,
        title: str,
        slug: str,
        color: str,
        sort_order: int,
        is_active: bool,
    ) -> Tag:
        with self._session_factory() as session:
            model = TagModel(
                title=title,
                slug=slug,
                color=color,
                sort_order=sort_order,
                is_active=is_active,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._to_tag(model)

    @handle_db_errors("update tag")
    def update_tag(self, tag_id: int, **kwargs: Any) -> Tag:
        with self._session_factory() as session:
            model = session.get(TagModel, tag_id)
            if model is None:
                raise LookupError(tag_id)
            for field in ("title", "slug", "color", "sort_order", "is_active"):
                if field in kwargs:
                    setattr(model, field, kwargs[field])
            session.commit()
            session.refresh(model)
            return self._to_tag(model)

    @handle_db_errors("delete tag")
    def delete_tag(self, tag_id: int) -> None:
        with self._session_factory() as session:
            model = session.get(TagModel, tag_id)
            if model is None:
                raise LookupError(tag_id)
            session.delete(model)
            session.commit()

    @handle_db_errors("effective attributes")
    def get_effective_attributes(self, category_id: int) -> list[CategoryAttribute]:
        with self._session_factory() as session:
            categories = {
                c.id: c
                for c in session.execute(select(CategoryModel)).scalars().all()
            }
            chain: list[CategoryModel] = []
            current = categories.get(category_id)
            while current is not None:
                chain.append(current)
                current = categories.get(current.parent_id) if current.parent_id else None
            chain.reverse()

            attrs: list[CategoryAttribute] = []
            for category in chain:
                attr_models = session.execute(
                    select(CategoryAttributeModel)
                    .where(CategoryAttributeModel.category_id == category.id)
                    .options(selectinload(CategoryAttributeModel.options))
                    .order_by(CategoryAttributeModel.sort_order, CategoryAttributeModel.title)
                ).scalars().all()
                for model in attr_models:
                    attrs.append(
                        self._to_attribute(
                            model,
                            inherited_from_id=category.id if category.id != category_id else None,
                            inherited_from_title=category.title if category.id != category_id else None,
                        )
                    )
            return attrs

    @handle_db_errors("get attribute")
    def get_attribute(self, attribute_id: int) -> CategoryAttribute | None:
        with self._session_factory() as session:
            model = session.execute(
                select(CategoryAttributeModel)
                .where(CategoryAttributeModel.id == attribute_id)
                .options(selectinload(CategoryAttributeModel.options))
            ).scalar_one_or_none()
            return self._to_attribute(model) if model else None

    @handle_db_errors("create attribute")
    def create_attribute(
        self,
        *,
        category_id: int,
        code: str,
        title: str,
        type: str,
        unit: str | None,
        is_required: bool,
        is_filterable: bool,
        is_public: bool,
        value_mode: str,
        sort_order: int,
        options: list[dict[str, Any]],
    ) -> CategoryAttribute:
        with self._session_factory() as session:
            model = CategoryAttributeModel(
                category_id=category_id,
                code=code,
                title=title,
                type=type,
                unit=unit,
                is_required=is_required,
                is_filterable=is_filterable,
                is_public=is_public,
                value_mode=value_mode,
                sort_order=sort_order,
            )
            session.add(model)
            session.flush()
            for idx, option in enumerate(options):
                session.add(
                    AttributeOptionModel(
                        attribute_id=model.id,
                        value=option.get("value", ""),
                        label=option.get("label", option.get("value", "")),
                        sort_order=option.get("sort_order", idx),
                    )
                )
            session.commit()
            session.refresh(model)
            model = session.execute(
                select(CategoryAttributeModel)
                .where(CategoryAttributeModel.id == model.id)
                .options(selectinload(CategoryAttributeModel.options))
            ).scalar_one()
            return self._to_attribute(model)

    @handle_db_errors("update attribute")
    def update_attribute(self, attribute_id: int, **kwargs: Any) -> CategoryAttribute:
        with self._session_factory() as session:
            model = session.get(CategoryAttributeModel, attribute_id)
            if model is None:
                raise LookupError(attribute_id)
            for field in (
                "code",
                "title",
                "type",
                "unit",
                "is_required",
                "is_filterable",
                "is_public",
                "value_mode",
                "sort_order",
            ):
                if field in kwargs:
                    setattr(model, field, kwargs[field])
            if "options" in kwargs:
                session.query(AttributeOptionModel).filter(
                    AttributeOptionModel.attribute_id == model.id
                ).delete()
                for idx, option in enumerate(kwargs["options"] or []):
                    session.add(
                        AttributeOptionModel(
                            attribute_id=model.id,
                            value=option.get("value", ""),
                            label=option.get("label", option.get("value", "")),
                            sort_order=option.get("sort_order", idx),
                        )
                    )
            session.commit()
            model = session.execute(
                select(CategoryAttributeModel)
                .where(CategoryAttributeModel.id == attribute_id)
                .options(selectinload(CategoryAttributeModel.options))
            ).scalar_one()
            return self._to_attribute(model)

    @handle_db_errors("delete attribute")
    def delete_attribute(self, attribute_id: int) -> None:
        with self._session_factory() as session:
            model = session.get(CategoryAttributeModel, attribute_id)
            if model is None:
                raise LookupError(attribute_id)
            session.delete(model)
            session.commit()
