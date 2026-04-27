from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .taxonomy import ProductAttributeValue, Tag


@dataclass(slots=True)
class Product:
    """
    Product Aggregate Root.
    """

    id: int
    title: str
    price: float
    description: str
    is_active: bool
    created_at: datetime
    images: list[str] = field(default_factory=list)
    category_id: int | None = None
    category_title: str = ""
    category_slug: str = ""
    category_path: list[str] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    attributes: list[ProductAttributeValue] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        id: int,
        title: str,
        price: float,
        description: str,
        images: list[str],
        category_id: int | None = None,
        tag_ids: list[int] | None = None,
        attribute_values: dict[str, Any] | None = None,
    ) -> "Product":
        return cls(
            id=id,
            title=title,
            price=price,
            description=description,
            is_active=True,
            created_at=datetime.now(),
            images=images,
            category_id=category_id,
        )
