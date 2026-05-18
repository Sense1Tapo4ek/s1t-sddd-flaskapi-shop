"""Unit tests for DeliveryInfo value object."""
import pytest

from ordering.domain import CourierAddressRequiredError, DeliveryInfo, DeliveryMethod


pytestmark = pytest.mark.unit


class TestDeliveryInfo:
    def test_pickup_requires_no_address(self):
        """
        Given method=PICKUP with no address,
        When creating DeliveryInfo,
        Then it succeeds and address defaults to empty string.
        """
        delivery = DeliveryInfo(method=DeliveryMethod.PICKUP)
        assert delivery.method is DeliveryMethod.PICKUP
        assert delivery.address == ""

    def test_courier_with_address_succeeds(self):
        """
        Given method=COURIER with a non-empty address,
        When creating DeliveryInfo,
        Then it succeeds.
        """
        delivery = DeliveryInfo(
            method=DeliveryMethod.COURIER,
            address="ул. Ленина, 1",
        )
        assert delivery.address == "ул. Ленина, 1"

    def test_courier_without_address_raises(self):
        """
        Given method=COURIER with an empty address,
        When creating DeliveryInfo,
        Then CourierAddressRequiredError is raised.
        """
        with pytest.raises(CourierAddressRequiredError) as exc_info:
            DeliveryInfo(method=DeliveryMethod.COURIER, address="")
        assert exc_info.value.code == "COURIER_ADDRESS_REQUIRED"

    def test_courier_whitespace_only_address_raises(self):
        """
        Given method=COURIER with a whitespace-only address,
        When creating DeliveryInfo,
        Then CourierAddressRequiredError is raised (whitespace is not an address).
        """
        with pytest.raises(CourierAddressRequiredError):
            DeliveryInfo(method=DeliveryMethod.COURIER, address="   ")

    def test_comment_defaults_to_empty(self):
        """
        Given no comment supplied,
        When creating DeliveryInfo,
        Then comment is empty string.
        """
        delivery = DeliveryInfo(method=DeliveryMethod.PICKUP)
        assert delivery.comment == ""

    def test_delivery_info_is_immutable(self):
        """
        Given a DeliveryInfo instance,
        When attempting to mutate a field,
        Then FrozenInstanceError is raised.
        """
        from dataclasses import FrozenInstanceError

        delivery = DeliveryInfo(method=DeliveryMethod.PICKUP)
        with pytest.raises(FrozenInstanceError):
            delivery.address = "changed"  # type: ignore[misc]
