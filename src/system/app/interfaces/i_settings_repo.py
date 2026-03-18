from typing import Protocol, runtime_checkable
from ...domain import SiteSettings


@runtime_checkable
class ISettingsRepo(Protocol):
    """
    Repository interface for SiteSettings.

    Since SiteSettings is a singleton, 'get' returns the single instance (or None),
    and 'save' persists that single instance.
    """

    def get(self) -> SiteSettings | None: ...

    def save(self, settings: SiteSettings) -> None:
        """Persist the aggregate state."""
        ...
