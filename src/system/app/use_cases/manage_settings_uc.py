import dataclasses
from dataclasses import dataclass

from ...domain import SiteSettings, SettingsNotFoundError
from ..commands import UpdateSettingsCommand
from ..interfaces import ISettingsRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ManageSettingsUseCase:
    """
    Updates system settings.
    If settings do not exist yet, it's treated as a conceptual error
    (though the repo usually ensures default creation, the use case should handle the flow).
    """

    _repo: ISettingsRepo

    def __call__(self, cmd: UpdateSettingsCommand) -> SiteSettings:
        # 1. Load
        settings = self._repo.get()
        if settings is None:
            # In a real system, we might want a 'InitializeSettingsUseCase',
            # but usually, the system bootstraps with default settings.
            raise SettingsNotFoundError()

        # 2. Apply Domain Logic (Mutation)
        # We pass only the fields present in the command
        updates = dataclasses.asdict(cmd)
        settings.update(**updates)

        # 3. Persist
        self._repo.save(settings)

        return settings
