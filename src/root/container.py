from dishka import Container, make_container
from dishka.integrations.flask import FlaskProvider

from shared.provider import InfraProvider
from catalog.provider import CatalogProvider
from ordering.provider import OrderingProvider
from access.provider import AccessProvider
from system.provider import SystemProvider


def build_container() -> Container:
    """
    Composition Root: Assembles the global DI container.
    """
    return make_container(
        FlaskProvider(),
        InfraProvider(),
        CatalogProvider(),
        OrderingProvider(),
        AccessProvider(),
        SystemProvider(),
    )
