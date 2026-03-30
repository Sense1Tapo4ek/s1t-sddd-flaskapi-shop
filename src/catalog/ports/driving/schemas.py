from pydantic import BaseModel, ConfigDict, Field
from shared.generics.pagination import PaginatedResult
from ...domain import Product


class CatalogQuery(BaseModel):
    model_config = ConfigDict(frozen=True)
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


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


class ProductOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    title: str
    price: float
    image: str

    @classmethod
    def from_domain(cls, product: Product) -> "ProductOut":
        image = product.images[0] if product.images else ""
        return cls(id=product.id, title=product.title, price=product.price, image=image)


class ProductDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    title: str
    price: float
    description: str
    images: list[str]
    created_at: str

    @classmethod
    def from_domain(cls, product: Product) -> "ProductDetailOut":
        return cls(
            id=product.id,
            title=product.title,
            price=product.price,
            description=product.description,
            images=product.images,
            created_at=product.created_at.strftime("%Y-%m-%d"),
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


