from dishka import Provider, Scope, provide

from catalog.config import CatalogConfig
from catalog.app import (
    CreateDemoDataUseCase,
    ManageCatalogUseCase,
    ManageTaxonomyUseCase,
    ViewCatalogUseCase,
)
from catalog.app.interfaces import IFileStorage, IProductRepo, ITaxonomyRepo
from catalog.ports.driven.sql_product_repo import SqlProductRepo
from catalog.ports.driven.sql_taxonomy_repo import SqlTaxonomyRepo
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
    def taxonomy_repo(self, impl: SqlTaxonomyRepo) -> ITaxonomyRepo:
        return impl

    @provide
    def storage(self, config: CatalogConfig) -> IFileStorage:
        return LocalFileStorage(_upload_dir=config.upload_dir)

    # Concretions
    sql_repo = provide(SqlProductRepo)
    sql_taxonomy_repo = provide(SqlTaxonomyRepo)

    # Use Cases
    view_uc = provide(ViewCatalogUseCase)
    manage_uc = provide(ManageCatalogUseCase)
    taxonomy_uc = provide(ManageTaxonomyUseCase)
    demo_data_uc = provide(CreateDemoDataUseCase)

    # Facade
    facade = provide(CatalogFacade)
