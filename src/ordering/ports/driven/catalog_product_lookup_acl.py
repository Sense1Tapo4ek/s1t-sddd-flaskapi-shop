"""Cross-context ACL: ordering → catalog.

Implements IProductLookupACL by delegating to CatalogFacade.get_detail().
Maps ProductDetailOut → ProductSnapshot. Only the fields needed for
order-placement are extracted (id, title, price, is_active).
"""
from dataclasses import dataclass
from decimal import Decimal

from catalog.ports.driving import CatalogFacade  # acl: catalog
from catalog.domain.errors import ProductNotFoundError

from ordering.app.interfaces.i_product_lookup_acl import IProductLookupACL, ProductSnapshot


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogProductLookupACL(IProductLookupACL):
    """Drives catalog context to snapshot product data at order placement."""

    _catalog: CatalogFacade

    def get(self, product_id: int) -> ProductSnapshot | None:
        try:
            detail = self._catalog.get_admin_detail(product_id)
        except ProductNotFoundError:
            # Product does not exist in catalog — treat as absent for order validation.
            return None
        if detail is None:
            return None
        return ProductSnapshot(
            id=detail.id,
            title=detail.title,
            unit_price=Decimal(str(detail.price)),
            is_active=detail.is_active,
        )
