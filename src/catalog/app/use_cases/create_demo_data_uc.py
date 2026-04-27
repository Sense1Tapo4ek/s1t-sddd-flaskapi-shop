from __future__ import annotations

import base64
import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from catalog.domain import Category, CategoryAttribute
from shared.generics.pagination import PaginationParams
from ..interfaces import IProductRepo, ITaxonomyRepo
from .manage_catalog_uc import ManageCatalogUseCase
from .manage_taxonomy_uc import ManageTaxonomyUseCase


DEMO_CATEGORIES: list[dict[str, Any]] = [
    {
        "title": "Одежда",
        "slug": "clothing",
        "sort_order": 10,
        "attributes": [
            {"title": "Размер", "code": "size", "type": "select", "is_required": True, "options": ["XS", "S", "M", "L", "XL"]},
            {"title": "Материал", "code": "material", "type": "text"},
        ],
        "children": [
            {
                "title": "Платья",
                "slug": "dresses",
                "sort_order": 10,
                "attributes": [
                    {"title": "Длина", "code": "length", "type": "select", "options": ["mini", "midi", "maxi"]},
                    {"title": "Сезон", "code": "season", "type": "multiselect", "options": ["spring", "summer", "autumn", "winter"]},
                ],
            },
            {"title": "Юбки", "slug": "skirts", "sort_order": 20},
        ],
    },
    {
        "title": "Обувь",
        "slug": "shoes",
        "sort_order": 20,
        "attributes": [
            {"title": "Размер обуви", "code": "shoe_size", "type": "number", "unit": "EU", "is_required": True},
            {"title": "Материал верха", "code": "upper_material", "type": "text"},
        ],
        "children": [
            {"title": "Кроссовки", "slug": "sneakers", "sort_order": 10},
            {"title": "Ботинки", "slug": "boots", "sort_order": 20},
        ],
    },
    {
        "title": "Аксессуары",
        "slug": "accessories",
        "sort_order": 30,
        "attributes": [
            {"title": "Бренд", "code": "brand", "type": "text"},
        ],
    },
]

DEMO_TAGS = [
    {"title": "Новинка", "slug": "new", "color": "#7c8c6e"},
    {"title": "Sale", "slug": "sale", "color": "#c4654a"},
    {"title": "Хит", "slug": "featured", "color": "#d4a853"},
]

ATTRIBUTE_VALUES = {
    "size": ["XS", "S", "M", "L", "XL"],
    "material": ["хлопок", "лен", "шерсть", "полиэстер"],
    "length": ["mini", "midi", "maxi"],
    "season": ["spring", "summer", "autumn", "winter"],
    "upper_material": ["кожа", "замша", "текстиль"],
    "brand": ["S1T", "Northline", "Forma"],
}

PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@dataclass(frozen=True, slots=True)
class DemoDataResult:
    categories_created: int = 0
    attributes_created: int = 0
    tags_created: int = 0
    products_created: int = 0
    images_downloaded: int = 0
    image_failures: int = 0

    def as_dict(self) -> dict[str, int | bool]:
        return {"success": True, **asdict(self)}


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDemoDataUseCase:
    _products: IProductRepo
    _taxonomy_repo: ITaxonomyRepo
    _catalog_uc: ManageCatalogUseCase
    _taxonomy_uc: ManageTaxonomyUseCase

    def __call__(self, *, products_per_leaf: int = 3) -> DemoDataResult:
        counters = {
            "categories_created": 0,
            "attributes_created": 0,
            "tags_created": 0,
            "products_created": 0,
            "images_downloaded": 0,
            "image_failures": 0,
        }
        for category_cfg in DEMO_CATEGORIES:
            self._ensure_category_tree(category_cfg, None, counters)
        tag_ids = self._ensure_tags(counters)
        for category in self._leaf_categories():
            self._ensure_category_products(
                category=category,
                tag_ids=tag_ids,
                count=products_per_leaf,
                counters=counters,
            )
        return DemoDataResult(**counters)

    def _ensure_category_tree(
        self,
        cfg: dict[str, Any],
        parent_id: int | None,
        counters: dict[str, int],
    ) -> Category:
        category = self._taxonomy_repo.get_category_by_slug(cfg["slug"])
        if category is None:
            category = self._taxonomy_uc.create_category(
                parent_id=parent_id,
                title=cfg["title"],
                slug=cfg["slug"],
                sort_order=int(cfg.get("sort_order", 0)),
            )
            counters["categories_created"] += 1

        for attr_cfg in cfg.get("attributes", []):
            if self._attribute_exists(category.id, attr_cfg["code"]):
                continue
            self._taxonomy_uc.create_attribute(
                category_id=category.id,
                code=attr_cfg["code"],
                title=attr_cfg["title"],
                type=attr_cfg.get("type", "text"),
                unit=attr_cfg.get("unit"),
                is_required=bool(attr_cfg.get("is_required", False)),
                options=[
                    {"value": str(option), "label": str(option), "sort_order": index}
                    for index, option in enumerate(attr_cfg.get("options", []))
                ],
            )
            counters["attributes_created"] += 1

        for child_cfg in cfg.get("children", []):
            self._ensure_category_tree(child_cfg, category.id, counters)
        return category

    def _attribute_exists(self, category_id: int, code: str) -> bool:
        return any(
            attr.code == code
            for attr in self._taxonomy_repo.get_effective_attributes(category_id)
        )

    def _ensure_tags(self, counters: dict[str, int]) -> list[int]:
        existing = {tag.slug: tag for tag in self._taxonomy_repo.list_tags(include_inactive=True)}
        tag_ids: list[int] = []
        for index, cfg in enumerate(DEMO_TAGS):
            tag = existing.get(cfg["slug"])
            if tag is None:
                tag = self._taxonomy_uc.create_tag(
                    title=cfg["title"],
                    slug=cfg["slug"],
                    color=cfg["color"],
                    sort_order=index,
                    is_active=True,
                )
                counters["tags_created"] += 1
            tag_ids.append(tag.id)
        return tag_ids

    def _leaf_categories(self) -> list[Category]:
        categories = self._taxonomy_repo.list_categories(include_inactive=False)
        parent_ids = {category.parent_id for category in categories if category.parent_id}
        leaves = [
            category
            for category in categories
            if category.id not in parent_ids and category.slug != "uncategorized"
        ]
        return sorted(leaves, key=lambda category: (category.sort_order, category.title))

    def _ensure_category_products(
        self,
        *,
        category: Category,
        tag_ids: list[int],
        count: int,
        counters: dict[str, int],
    ) -> None:
        attributes = self._taxonomy_repo.get_effective_attributes(category.id)
        for index in range(1, count + 1):
            title = f"Demo {category.title} #{index}"
            existing = self._products.search(
                "",
                PaginationParams(
                    page=1,
                    limit=1,
                    filters={"title": title, "category_id": str(category.id)},
                ),
            )
            if existing.total:
                continue

            images = self._build_images(category.slug, index, counters)
            self._catalog_uc.create(
                title=title,
                price=round(49 + index * 17 + len(category.title) * 3.7, 2),
                description=f"Демо-товар для категории «{category.title}».",
                images=images,
                category_id=category.id,
                tag_ids=self._pick_tags(tag_ids, index),
                attribute_values={
                    attr.code: self._value_for_attribute(attr, index)
                    for attr in attributes
                    if attr.is_required or attr.is_public
                },
            )
            counters["products_created"] += 1

    def _build_images(
        self,
        category_slug: str,
        index: int,
        counters: dict[str, int],
    ) -> list[tuple[str, bytes]]:
        counters["images_downloaded"] += 1
        return [(f"{category_slug}-{index}.png", PLACEHOLDER_PNG)]

    def _pick_tags(self, tag_ids: list[int], index: int) -> list[int]:
        if not tag_ids:
            return []
        random.seed(index)
        count = min(len(tag_ids), 1 + (index % 2))
        return random.sample(tag_ids, count)

    def _value_for_attribute(self, attr: CategoryAttribute, index: int) -> Any:
        configured = ATTRIBUTE_VALUES.get(attr.code)
        if attr.type == "number":
            return 36 + (index % 10) if attr.code == "shoe_size" else index * 10
        if attr.type == "boolean":
            return index % 2 == 0
        if attr.type == "date":
            return (date.today() + timedelta(days=index)).isoformat()
        if attr.type == "url":
            return f"https://example.com/demo/{attr.code}/{index}"
        if attr.type == "select":
            options = [option.value for option in attr.options] or list(configured or [])
            return options[index % len(options)] if options else f"value-{index}"
        if attr.type == "multiselect":
            options = [option.value for option in attr.options] or list(configured or [])
            return options[: min(2, len(options))] if options else [f"value-{index}"]
        if configured:
            return configured[index % len(configured)]
        return f"{attr.title} {index}"
