import pytest

from catalog.domain import ATTRIBUTE_TYPES, CategoryAttribute


def _attribute(attribute_type: str) -> CategoryAttribute:
    return CategoryAttribute(
        id=1,
        category_id=10,
        code="size",
        title="Size",
        type=attribute_type,
        unit=None,
        is_required=True,
        is_filterable=True,
        is_public=True,
        sort_order=0,
    )


@pytest.mark.unit
class TestCategoryAttributeType:
    @pytest.mark.parametrize("attribute_type", sorted(ATTRIBUTE_TYPES))
    def test_supported_attribute_type_is_valid(self, attribute_type):
        """
        Given a category attribute with a supported type,
        When validating the attribute type,
        Then validation succeeds.
        """
        # Arrange
        attribute = _attribute(attribute_type)

        # Act
        attribute.validate_type()

        # Assert
        assert attribute.type == attribute_type

    def test_unsupported_attribute_type_is_rejected(self):
        """
        Given a category attribute with an unsupported type,
        When validating the attribute type,
        Then validation rejects the attribute.
        """
        # Arrange
        attribute = _attribute("json")

        # Act / Assert
        with pytest.raises(ValueError, match="Unsupported attribute type: json"):
            attribute.validate_type()
