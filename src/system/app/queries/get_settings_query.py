from dataclasses import dataclass

from ...domain import SiteSettings, SettingsNotFoundError
from ..interfaces import ISettingsRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class GetSettingsQuery:
    _repo: ISettingsRepo

    def __call__(self) -> SiteSettings:
        settings = self._repo.get()
        if settings is None:
            raise SettingsNotFoundError()
        return settings
