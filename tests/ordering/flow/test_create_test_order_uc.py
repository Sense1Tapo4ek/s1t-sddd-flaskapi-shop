"""Flow tests for CreateTestOrderUseCase.

Mocks IOrderRepo and IProductLookupACL. Verifies:
  - returns the new order id when an active product exists,
  - raises ProductNotFoundForOrderError when no active product is found,
  - skips inactive products and picks the next active one.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from ordering.app.errors import ProductNotFoundForOrderError
from ordering.app.interfaces import IOrderRepo, IProductLookupACL, ProductSnapshot
from ordering.app.use_cases.create_test_order_uc import CreateTestOrderUseCase
from ordering.domain import Order, OrderStatus


pytestmark = pytest.mark.flow


def _snapshot(*, id: int, is_active: bool = True) -> ProductSnapshot:
    return ProductSnapshot(
        id=id,
        title=f"Product {id}",
        unit_price=Decimal("19.99"),
        is_active=is_active,
    )


class _FakeRepo:
    """Captures the order passed to save() and stamps an id, matching SqlOrderRepo."""

    def __init__(self) -> None:
        self.saved: Order | None = None

    def next_id(self) -> int:
        return 0

    def save(self, order: Order) -> None:
        order.id = 42
        self.saved = order


class TestCreateTestOrderHappyPath:
    def test_creates_one_order_with_first_active_product(self):
        """
        Given a catalog with an active product at id=1,
        When CreateTestOrderUseCase is invoked,
        Then it persists exactly one order containing that product and returns its id.
        """
        # Arrange
        repo = _FakeRepo()
        acl = MagicMock(spec=IProductLookupACL)
        acl.get.side_effect = lambda pid: _snapshot(id=pid) if pid == 1 else None
        uc = CreateTestOrderUseCase(_orders=repo, _product_acl=acl)

        # Act
        result = uc()

        # Assert
        assert result == 42
        assert repo.saved is not None
        assert repo.saved.status is OrderStatus.NEW
        assert len(repo.saved.items) == 1
        assert repo.saved.items[0].product_id == 1
        assert repo.saved.items[0].quantity == 1

    def test_skips_inactive_products(self):
        """
        Given the first product is inactive and the second is active,
        When CreateTestOrderUseCase scans the catalog,
        Then it skips the inactive one and uses the active product.
        """
        # Arrange
        repo = _FakeRepo()
        acl = MagicMock(spec=IProductLookupACL)
        catalog: dict[int, ProductSnapshot] = {
            1: _snapshot(id=1, is_active=False),
            2: _snapshot(id=2, is_active=True),
        }
        acl.get.side_effect = lambda pid: catalog.get(pid)
        uc = CreateTestOrderUseCase(_orders=repo, _product_acl=acl)

        # Act
        uc()

        # Assert
        assert repo.saved is not None
        assert repo.saved.items[0].product_id == 2


class TestCreateTestOrderNoCatalog:
    def test_raises_when_no_active_product_found(self):
        """
        Given a catalog with no active products,
        When CreateTestOrderUseCase is invoked,
        Then ProductNotFoundForOrderError is raised and nothing is persisted.
        """
        # Arrange
        repo = _FakeRepo()
        acl = MagicMock(spec=IProductLookupACL)
        acl.get.return_value = None
        uc = CreateTestOrderUseCase(_orders=repo, _product_acl=acl)

        # Act + Assert
        with pytest.raises(ProductNotFoundForOrderError):
            uc()
        assert repo.saved is None
