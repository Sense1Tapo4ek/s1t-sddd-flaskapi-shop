from datetime import datetime

import pytest

from catalog.app.use_cases.view_catalog_uc import ViewCatalogUseCase
from catalog.domain import Product, ProductNotFoundError
from shared.generics.pagination import PaginatedResult, PaginationParams


def _product(product_id: int, *, is_active: bool = True) -> Product:
    return Product(
        id=product_id,
        title=f"Product {product_id}",
        price=100.0,
        description="Catalog product",
        is_active=is_active,
        created_at=datetime(2024, 1, 1),
        images=[],
    )


class FakeProductRepo:
    def __init__(self, products: dict[int, Product] | None = None) -> None:
        self.products = products or {}
        self.paginated_result = PaginatedResult(
            items=list(self.products.values()),
            total=len(self.products),
            page=1,
            limit=20,
        )
        self.get_by_id_calls: list[int] = []
        self.get_paginated_calls: list[PaginationParams] = []
        self.search_calls: list[tuple[str, PaginationParams]] = []
        self.get_random_calls: list[int] = []

    def get_by_id(self, product_id: int) -> Product | None:
        self.get_by_id_calls.append(product_id)
        return self.products.get(product_id)

    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Product]:
        self.get_paginated_calls.append(params)
        return self.paginated_result

    def search(self, query: str, params: PaginationParams) -> PaginatedResult[Product]:
        self.search_calls.append((query, params))
        return self.paginated_result

    def get_random(self, limit: int) -> list[Product]:
        self.get_random_calls.append(limit)
        return list(self.products.values())[:limit]

    def create(self, product: Product) -> Product:
        raise NotImplementedError

    def update(self, product: Product) -> Product:
        raise NotImplementedError

    def delete(self, product_id: int) -> bool:
        raise NotImplementedError

    def swap_ids(self, id_a: int, id_b: int) -> None:
        raise NotImplementedError


@pytest.mark.flow
class TestViewCatalogPagination:
    def test_get_paginated_without_filters_uses_regular_listing_and_forces_active(self):
        """
        Given no catalog filters,
        When requesting a paginated product list,
        Then the use case calls get_paginated with is_active forced to true.
        """
        # Arrange
        repo = FakeProductRepo()
        use_case = ViewCatalogUseCase(_repo=repo)

        # Act
        result = use_case.get_paginated(page=2, limit=5)

        # Assert
        assert result is repo.paginated_result
        assert repo.search_calls == []
        assert len(repo.get_paginated_calls) == 1
        params = repo.get_paginated_calls[0]
        assert params.page == 2
        assert params.limit == 5
        assert params.filters == {"is_active": True}

    def test_get_paginated_with_filters_uses_search_and_overrides_inactive_filter(self):
        """
        Given caller filters that try to include inactive products,
        When requesting a paginated product list,
        Then the use case searches with is_active overwritten to true.
        """
        # Arrange
        repo = FakeProductRepo()
        use_case = ViewCatalogUseCase(_repo=repo)
        filters = {"category_id": 10, "is_active": False}

        # Act
        result = use_case.get_paginated(filters=filters)

        # Assert
        assert result is repo.paginated_result
        assert repo.get_paginated_calls == []
        assert len(repo.search_calls) == 1
        query, params = repo.search_calls[0]
        assert query == ""
        assert params.filters == {"category_id": 10, "is_active": True}
        assert filters["is_active"] is False


@pytest.mark.flow
class TestViewCatalogDetail:
    def test_get_detail_rejects_inactive_product_unless_explicitly_included(self):
        """
        Given an inactive product exists,
        When reading product detail with and without include_inactive,
        Then the use case rejects the public read and allows the explicit admin read.
        """
        # Arrange
        product = _product(7, is_active=False)
        repo = FakeProductRepo({7: product})
        use_case = ViewCatalogUseCase(_repo=repo)

        # Act
        with pytest.raises(ProductNotFoundError) as exc_info:
            use_case.get_detail(7)
        included = use_case.get_detail(7, include_inactive=True)

        # Assert
        assert exc_info.value.code == "PRODUCT_NOT_FOUND"
        assert included is product
        assert repo.get_by_id_calls == [7, 7]

    def test_get_detail_rejects_missing_product(self):
        """
        Given a product id absent from the catalog,
        When reading product detail,
        Then the use case raises product-not-found.
        """
        # Arrange
        repo = FakeProductRepo()
        use_case = ViewCatalogUseCase(_repo=repo)

        # Act
        with pytest.raises(ProductNotFoundError) as exc_info:
            use_case.get_detail(404)

        # Assert
        assert exc_info.value.code == "PRODUCT_NOT_FOUND"
        assert repo.get_by_id_calls == [404]


@pytest.mark.flow
class TestViewCatalogRandom:
    def test_get_random_filters_inactive_products_from_public_result(self):
        """
        Given the repository returns both active and inactive random products,
        When requesting public random products,
        Then the use case returns only active products.
        """
        # Arrange
        active = _product(1, is_active=True)
        inactive = _product(2, is_active=False)
        repo = FakeProductRepo({1: active, 2: inactive})
        use_case = ViewCatalogUseCase(_repo=repo)

        # Act
        result = use_case.get_random(limit=4)

        # Assert
        assert result == [active]
        assert repo.get_random_calls == [4]
