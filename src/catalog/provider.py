from dishka import Provider, Scope, provide

from catalog.config import CatalogConfig
from catalog.app import ViewCatalogUseCase, ManageCatalogUseCase
from catalog.app.interfaces import IProductRepo, IFileStorage
from catalog.ports.driven.sql_product_repo import SqlProductRepo
from catalog.ports.driving import CatalogFacade
from shared.adapters.driven.file_storage import LocalFileStorage


class CatalogProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> CatalogConfig:
        return CatalogConfig()

    @provide
    def repo(self, impl: SqlProductRepo) -> IProductRepo:
        return impl

    @provide
    def storage(self, config: CatalogConfig) -> IFileStorage:
        return LocalFileStorage(_upload_dir=config.upload_dir)

    # Concretions
    sql_repo = provide(SqlProductRepo)

    # Use Cases
    view_uc = provide(ViewCatalogUseCase)
    manage_uc = provide(ManageCatalogUseCase)

    # Facade
    facade = provide(CatalogFacade)
