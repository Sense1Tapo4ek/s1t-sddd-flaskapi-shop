from dataclasses import dataclass, field
from datetime import datetime


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

    @classmethod
    def create(
        cls, id: int, title: str, price: float, description: str, images: list[str]
    ) -> "Product":
        return cls(
            id=id,
            title=title,
            price=price,
            description=description,
            is_active=True,
            created_at=datetime.now(),
            images=images,
        )
