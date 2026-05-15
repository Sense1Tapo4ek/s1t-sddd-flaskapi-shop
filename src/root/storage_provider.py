from dishka import Provider, Scope, provide

from catalog.app.interfaces import IFileStorage
from catalog.config import CatalogConfig
from system.adapters.driven import StorageRouter
from system.app.interfaces import IStorageCacheInvalidator, IStorageSettingsRepo


class StorageProvider(Provider):
    """
    Composition-root provider that wires the cross-context StorageRouter.

    Lives at the root level (not inside any bounded context) because it binds
    a system-context adapter to a catalog-context Protocol — a cross-context
    concrete-to-Protocol mapping that must not appear inside a context provider
    per S-DDD rules.
    """

    scope = Scope.APP

    @provide
    def storage_router(
        self,
        config: CatalogConfig,
        settings_repo: IStorageSettingsRepo,
    ) -> StorageRouter:
        return StorageRouter(
            _settings_repo=settings_repo,
            _local_fallback_dir=config.upload_dir,
        )

    @provide
    def file_storage(self, router: StorageRouter) -> IFileStorage:
        return router

    @provide
    def cache_invalidator(self, router: StorageRouter) -> IStorageCacheInvalidator:
        return router
