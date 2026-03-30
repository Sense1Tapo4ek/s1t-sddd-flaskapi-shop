from dataclasses import dataclass
from typing import ClassVar
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload

from shared.generics.errors import DrivenPortError
from shared.generics.pagination import PaginatedResult, PaginationParams
from shared.adapters.driven import SqlBaseRepo
from shared.helpers.db import handle_db_errors

from catalog.app.interfaces import IProductRepo
from catalog.domain import Product
from catalog.adapters.driven.db.models import ProductModel, ProductImageModel


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlProductRepo(SqlBaseRepo[Product, ProductModel], IProductRepo):

    _model_class: ClassVar[type[ProductModel]] = ProductModel

    def _to_domain(self, model: ProductModel) -> Product:
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
        with self._session_factory() as session:
            model = session.execute(
                select(ProductModel)
                .where(ProductModel.id == product_id)
                .options(selectinload(ProductModel.images))
            ).scalar_one_or_none()
            return self._to_domain(model) if model else None

    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Product]:
        with self._session_factory() as session:
            stmt = select(ProductModel).where(ProductModel.is_active)
            return self._paginate(
                session=session, stmt=stmt, params=params,
                default_sort="id",
                load_options=[selectinload(ProductModel.images)],
            )

    def get_random(self, limit: int) -> list[Product]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ProductModel)
                .where(ProductModel.is_active)
                .options(selectinload(ProductModel.images))
                .order_by(func.random())
                .limit(limit)
            ).scalars().all()
            return [self._to_domain(r) for r in rows]

    def search(self, query: str, params: PaginationParams) -> PaginatedResult[Product]:
        with self._session_factory() as session:
            stmt = select(ProductModel)
            if query:
                stmt = stmt.where(func.lower(ProductModel.title).contains(func.lower(query)))
            return self._paginate(
                session=session, stmt=stmt, params=params,
                default_sort="id",
                load_options=[selectinload(ProductModel.images)],
            )

    @handle_db_errors("create product")
    def create(self, product: Product) -> Product:
        with self._session_factory() as session:
            model = ProductModel(
                title=product.title, price=product.price,
                description=product.description, is_active=product.is_active,
            )
            session.add(model)
            session.flush()
            for path in product.images:
                session.add(ProductImageModel(product_id=model.id, file_path=path))
            session.commit()
            session.refresh(model)
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
            session.query(ProductImageModel).filter(
                ProductImageModel.product_id == model.id
            ).delete()
            for path in product.images:
                session.add(ProductImageModel(product_id=model.id, file_path=path))
            session.commit()
            session.refresh(model)
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
            conn = session.connection()
            temp = -1
            conn.execute(text("PRAGMA foreign_keys = OFF"))
            conn.execute(text("UPDATE product_images SET product_id = :t WHERE product_id = :a"), {"t": temp, "a": id_a})
            conn.execute(text("UPDATE products SET id = :t WHERE id = :a"), {"t": temp, "a": id_a})
            conn.execute(text("UPDATE product_images SET product_id = :a WHERE product_id = :b"), {"a": id_a, "b": id_b})
            conn.execute(text("UPDATE products SET id = :a WHERE id = :b"), {"a": id_a, "b": id_b})
            conn.execute(text("UPDATE product_images SET product_id = :b WHERE product_id = :t"), {"b": id_b, "t": temp})
            conn.execute(text("UPDATE products SET id = :b WHERE id = :t"), {"b": id_b, "t": temp})
            conn.execute(text("PRAGMA foreign_keys = ON"))
            session.commit()
