import pytest

from catalog.domain import Product


@pytest.mark.unit
class TestProductCreation:
    def test_created_product_is_active_by_default(self):
        """
        Given valid product data,
        When creating a product,
        Then the product is active by default and keeps its base fields.
        """
        # Arrange
        images = ["main.png", "side.png"]

        # Act
        product = Product.create(
            id=1,
            title="Sneakers",
            price=120.0,
            description="Daily sneakers",
            images=images,
            category_id=7,
        )

        # Assert
        assert product.is_active is True
        assert product.category_id == 7
        assert product.images == images
