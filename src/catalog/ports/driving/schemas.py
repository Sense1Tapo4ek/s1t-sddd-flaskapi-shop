from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from shared.generics.pagination import PaginatedResult
from ...domain import (
    AttributeOption,
    Category,
    CategoryAttribute,
    Product,
    ProductAttributeValue,
    Tag,
)


class CatalogQuery(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    category: str | None = None
    category_id: int | None = Field(None, ge=1)
    include_descendants: bool = False
    tags: str | None = None


class RandomQuery(BaseModel):
    model_config = ConfigDict(frozen=True)
    limit: int = Field(4, ge=1, le=20)


class DeleteImageIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    image_path: str


class ProductSearchQuery(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    q: str = ""
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sort_by: str | None = None
    sort_dir: str = Field("asc", pattern="^(asc|desc)$")
    category: str | None = None
    category_id: int | None = Field(None, ge=1)
    include_descendants: bool = False
    tags: str | None = None


class ProductTaxonomyIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    category_id: int | None = Field(None, ge=1)
    tag_ids: list[int] = Field(default_factory=list)
    attribute_values: dict[str, Any] = Field(default_factory=dict)


class CategoryCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_id: int | None = Field(None, ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    description: str = ""
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_id: int | None = Field(None, ge=1)
    title: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryMoveIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_id: int | None = Field(None, ge=1)
    sort_order: int | None = None


class TagCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    color: str = Field("#7c8c6e", max_length=32)
    sort_order: int = 0
    is_active: bool = True


class TagUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=32)
    sort_order: int | None = None
    is_active: bool | None = None


class AttributeOptionIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str = Field(..., min_length=1, max_length=255)
    label: str = Field(..., min_length=1, max_length=255)
    sort_order: int = 0


class CategoryAttributeCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., max_length=32)
    unit: str | None = Field(None, max_length=50)
    is_required: bool = False
    value_mode: str = Field("single", pattern="^(single|multiple)$")
    sort_order: int = 0
    options: list[AttributeOptionIn] = Field(default_factory=list)


class CategoryAttributeUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str | None = Field(None, min_length=1, max_length=100)
    title: str | None = Field(None, min_length=1, max_length=255)
    type: str | None = Field(None, max_length=32)
    unit: str | None = Field(None, max_length=50)
    is_required: bool | None = None
    value_mode: str | None = Field(None, pattern="^(single|multiple)$")
    sort_order: int | None = None
    options: list[AttributeOptionIn] | None = None


class CategorySummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    slug: str

    @classmethod
    def from_product(cls, product: Product) -> "CategorySummaryOut | None":
        if product.category_id is None:
            return None
        return cls(
            id=product.category_id,
            title=product.category_title,
            slug=product.category_slug,
        )


class CategoryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    parent_id: int | None
    title: str
    slug: str
    description: str
    sort_order: int
    is_active: bool
    created_at: str | None = None
    product_count: int = 0
    children: list["CategoryOut"] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, category: Category) -> "CategoryOut":
        return cls(
            id=category.id,
            parent_id=category.parent_id,
            title=category.title,
            slug=category.slug,
            description=category.description,
            sort_order=category.sort_order,
            is_active=category.is_active,
            created_at=(
                category.created_at.isoformat() if category.created_at else None
            ),
            product_count=category.product_count,
            children=[cls.from_domain(child) for child in category.children],
        )


class TagSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    slug: str
    color: str

    @classmethod
    def from_domain(cls, tag: Tag) -> "TagSummaryOut":
        return cls(id=tag.id, title=tag.title, slug=tag.slug, color=tag.color)


class TagOut(TagSummaryOut):
    sort_order: int
    is_active: bool
    created_at: str | None = None
    product_count: int = 0

    @classmethod
    def from_domain(cls, tag: Tag) -> "TagOut":
        return cls(
            id=tag.id,
            title=tag.title,
            slug=tag.slug,
            color=tag.color,
            sort_order=tag.sort_order,
            is_active=tag.is_active,
            created_at=tag.created_at.isoformat() if tag.created_at else None,
            product_count=tag.product_count,
        )


class AttributeOptionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    attribute_id: int
    value: str
    label: str
    sort_order: int

    @classmethod
    def from_domain(cls, option: AttributeOption) -> "AttributeOptionOut":
        return cls(
            id=option.id,
            attribute_id=option.attribute_id,
            value=option.value,
            label=option.label,
            sort_order=option.sort_order,
        )


class CategoryAttributeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    category_id: int
    code: str
    title: str
    type: str
    unit: str | None
    is_required: bool
    is_filterable: bool
    is_public: bool
    value_mode: str
    sort_order: int
    inherited_from_id: int | None = None
    inherited_from_title: str | None = None
    options: list[AttributeOptionOut] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, attribute: CategoryAttribute) -> "CategoryAttributeOut":
        return cls(
            id=attribute.id,
            category_id=attribute.category_id,
            code=attribute.code,
            title=attribute.title,
            type=attribute.type,
            unit=attribute.unit,
            is_required=attribute.is_required,
            is_filterable=attribute.is_filterable,
            is_public=attribute.is_public,
            value_mode=attribute.value_mode,
            sort_order=attribute.sort_order,
            inherited_from_id=attribute.inherited_from_id,
            inherited_from_title=attribute.inherited_from_title,
            options=[AttributeOptionOut.from_domain(o) for o in attribute.options],
        )


class CategoryAttributesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[CategoryAttributeOut]
    inherited: list[CategoryAttributeOut]
    own: list[CategoryAttributeOut]

    @classmethod
    def from_domain(
        cls, category_id: int, attributes: list[CategoryAttribute]
    ) -> "CategoryAttributesOut":
        items = [CategoryAttributeOut.from_domain(a) for a in attributes]
        inherited = [
            attr
            for attr in items
            if attr.category_id != category_id or attr.inherited_from_id is not None
        ]
        own = [
            attr
            for attr in items
            if attr.category_id == category_id and attr.inherited_from_id is None
        ]
        return cls(items=items, inherited=inherited, own=own)


class ProductAttributeValueOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    attribute_id: int
    code: str
    title: str
    type: str
    value: Any
    unit: str | None = None

    @classmethod
    def from_domain(
        cls, value: ProductAttributeValue
    ) -> "ProductAttributeValueOut":
        return cls(
            attribute_id=value.attribute_id,
            code=value.code,
            title=value.title,
            type=value.type,
            value=value.value,
            unit=value.unit,
        )


class ProductOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    title: str
    price: float
    image: str
    category_id: int | None = None
    category: CategorySummaryOut | None = None
    tags: list[TagSummaryOut] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, product: Product) -> "ProductOut":
        image = product.images[0] if product.images else ""
        return cls(
            id=product.id,
            title=product.title,
            price=product.price,
            image=image,
            category_id=product.category_id,
            category=CategorySummaryOut.from_product(product),
            tags=[TagSummaryOut.from_domain(tag) for tag in product.tags],
        )


class ProductDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    title: str
    price: float
    description: str
    images: list[str]
    created_at: str
    category_id: int | None = None
    category: CategorySummaryOut | None = None
    category_path: list[str] = Field(default_factory=list)
    tags: list[TagSummaryOut] = Field(default_factory=list)
    attributes: list[ProductAttributeValueOut] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, product: Product) -> "ProductDetailOut":
        return cls(
            id=product.id,
            title=product.title,
            price=product.price,
            description=product.description,
            images=product.images,
            created_at=product.created_at.strftime("%Y-%m-%d"),
            category_id=product.category_id,
            category=CategorySummaryOut.from_product(product),
            category_path=product.category_path,
            tags=[TagSummaryOut.from_domain(tag) for tag in product.tags],
            attributes=[
                ProductAttributeValueOut.from_domain(value)
                for value in product.attributes
            ],
        )


class CatalogListOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[ProductOut]
    total: int
    page: int
    limit: int

    @classmethod
    def from_domain(cls, result: PaginatedResult[Product]) -> "CatalogListOut":
        return cls(
            items=[ProductOut.from_domain(p) for p in result.items],
            total=result.total,
            page=result.page,
            limit=result.limit,
        )


class AdminProductListOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[ProductDetailOut]
    total: int

    @classmethod
    def from_domain(cls, result: PaginatedResult[Product]) -> "AdminProductListOut":
        return cls(
            items=[ProductDetailOut.from_domain(p) for p in result.items],
            total=result.total,
        )


class SwapSortOrderIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    id_a: int
    id_b: int
