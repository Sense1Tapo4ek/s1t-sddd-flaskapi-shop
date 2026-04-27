from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


ATTRIBUTE_TYPES = {
    "text",
    "number",
    "boolean",
    "select",
    "multiselect",
    "date",
    "url",
    "file",
    "image",
}

ATTRIBUTE_VALUE_MODES = {"single", "multiple"}


@dataclass(slots=True)
class Category:
    id: int
    parent_id: int | None
    title: str
    slug: str
    description: str
    sort_order: int
    is_active: bool
    created_at: datetime | None = None
    product_count: int = 0
    children: list["Category"] = field(default_factory=list)


@dataclass(slots=True)
class Tag:
    id: int
    title: str
    slug: str
    color: str
    sort_order: int
    is_active: bool
    created_at: datetime | None = None
    product_count: int = 0


@dataclass(slots=True)
class AttributeOption:
    id: int
    attribute_id: int
    value: str
    label: str
    sort_order: int


@dataclass(slots=True)
class CategoryAttribute:
    id: int
    category_id: int
    code: str
    title: str
    type: str
    unit: str | None
    is_required: bool
    is_filterable: bool
    is_public: bool
    sort_order: int
    value_mode: str = "single"
    inherited_from_id: int | None = None
    inherited_from_title: str | None = None
    options: list[AttributeOption] = field(default_factory=list)

    def validate_type(self) -> None:
        if self.type not in ATTRIBUTE_TYPES:
            raise ValueError(f"Unsupported attribute type: {self.type}")
        if self.value_mode not in ATTRIBUTE_VALUE_MODES:
            raise ValueError(f"Unsupported attribute value mode: {self.value_mode}")


@dataclass(slots=True)
class ProductAttributeValue:
    attribute_id: int
    code: str
    title: str
    type: str
    value: Any
    unit: str | None = None
