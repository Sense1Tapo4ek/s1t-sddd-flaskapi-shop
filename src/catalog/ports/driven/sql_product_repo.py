from dataclasses import dataclass
from typing import Callable, ClassVar
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from shared.generics.errors import DrivenPortError
from shared.generics.pagination import PaginatedResult, PaginationParams
from shared.adapters.driven import SqlBaseRepo

from catalog.app.interfaces import IProductRepo
from catalog.domain import Product
from catalog.adapters.driven.db.models import ProductModel, ProductImageModel


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlProductRepo(SqlBaseRepo[Product, ProductModel], IProductRepo):
    """
    SQLAlchemy implementation of the Product Repository.
    Handles data persistence and retrieval for the Catalog context.
    """

    _model_class: ClassVar[type[ProductModel]] = ProductModel

    def _to_domain(self, model: ProductModel) -> Product:
        """Converts an SQLAlchemy ProductModel to a Domain Product aggregate."""
        return Product(
            id=model.id,
            title=model.title,
            price=model.price,
            description=model.description,
            is_active=model.is_active,
            created_at=model.created_at,
            images=[img.file_path for img in model.images],
        )

    def get_by_id(self, product_id: int) -> Product | None:
        """Retrieves a product by its unique identifier, including its images."""
        with self._session_factory() as session:
            model = session.execute(
                select(ProductModel)
                .where(ProductModel.id == product_id)
                .options(selectinload(ProductModel.images))
            ).scalar_one_or_none()
            return self._to_domain(model) if model else None

    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Product]:
        """Retrieves a paginated list of active products."""
        with self._session_factory() as session:
            stmt = select(ProductModel).where(ProductModel.is_active)
            return self._paginate(
                session=session,
                stmt=stmt,
                params=params,
                default_sort="created_at",
                load_options=[selectinload(ProductModel.images)],
            )

    def get_random(self, limit: int) -> list[Product]:
        """Retrieves a specified number of random active products."""
        with self._session_factory() as session:
            rows = (
                session.execute(
                    select(ProductModel)
                    .where(ProductModel.is_active)
                    .options(selectinload(ProductModel.images))
                    .order_by(func.random())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [self._to_domain(r) for r in rows]

    def search(self, query: str, params: PaginationParams) -> PaginatedResult[Product]:
        """
        Executes a global text search alongside dynamic attribute filtering.
        Delegates pagination and filter application to the base repository.
        """
        with self._session_factory() as session:
            stmt = select(ProductModel)

            if query:
                stmt = stmt.where(
                    func.lower(ProductModel.title).contains(func.lower(query))
                )

            return self._paginate(
                session=session,
                stmt=stmt,
                params=params,
                default_sort="created_at",
                load_options=[selectinload(ProductModel.images)],
            )

    def create(self, product: Product) -> Product:
        """Persists a new product and its associated images."""
        try:
            with self._session_factory() as session:
                model = ProductModel(
                    title=product.title,
                    price=product.price,
                    description=product.description,
                    is_active=product.is_active,
                )
                session.add(model)
                session.flush()

                for path in product.images:
                    session.add(ProductImageModel(product_id=model.id, file_path=path))

                session.commit()
                session.refresh(model)
                return self._to_domain(model)
        except Exception as e:
            raise DrivenPortError(f"DB Error create product: {e}")

    def update(self, product: Product) -> Product:
        """Updates an existing product and strictly synchronizes its image relations."""
        try:
            with self._session_factory() as session:
                model = session.get(ProductModel, product.id)
                if not model:
                    raise DrivenPortError(f"Product {product.id} missing during update")

                model.title = product.title
                model.price = product.price
                model.description = product.description

                session.query(ProductImageModel).filter(
                    ProductImageModel.product_id == model.id
                ).delete()

                for path in product.images:
                    session.add(ProductImageModel(product_id=model.id, file_path=path))

                session.commit()
                session.refresh(model)
                return self._to_domain(model)
        except Exception as e:
            raise DrivenPortError(f"DB Error update product: {e}")

    def delete(self, product_id: int) -> bool:
        """Removes a product from the database by its identifier."""
        try:
            with self._session_factory() as session:
                model = session.get(ProductModel, product_id)
                if model:
                    session.delete(model)
                    session.commit()
                    return True
                return False
        except Exception as e:
            raise DrivenPortError(f"DB Error delete product: {e}")
