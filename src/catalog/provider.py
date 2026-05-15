from dishka import Provider, Scope, provide

from catalog.app import (
    BulkAssignProductsCategoryUseCase,
    BulkAssignProductsTagsUseCase,
    BulkDeleteProductsUseCase,
    BulkDeleteTagsUseCase,
    BulkSetProductsActiveUseCase,
    BulkSetTagsActiveUseCase,
    CreateDemoDataUseCase,
    ManageCatalogUseCase,
    ManageTaxonomyUseCase,
    ViewCatalogUseCase,
)
from catalog.app.interfaces import IProductRepo, ITaxonomyRepo
from catalog.config import CatalogConfig
from catalog.ports.driven.sql_product_repo import SqlProductRepo
from catalog.ports.driven.sql_taxonomy_repo import SqlTaxonomyRepo
from catalog.ports.driving import CatalogFacade


class CatalogProvider(Provider):
    """
    Catalog context wiring.

    NOTE: `IFileStorage` is bound at the composition root by `StorageProvider`,
    not here — it requires a cross-context adapter (`system.adapters.driven.StorageRouter`)
    which a context provider must not import directly per S-DDD rules.
    """

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

    # Concretions
    sql_repo = provide(SqlProductRepo)
    sql_taxonomy_repo = provide(SqlTaxonomyRepo)

    # Use Cases
    view_uc = provide(ViewCatalogUseCase)
    manage_uc = provide(ManageCatalogUseCase)
    taxonomy_uc = provide(ManageTaxonomyUseCase)
    demo_data_uc = provide(CreateDemoDataUseCase)
    bulk_set_active_uc = provide(BulkSetProductsActiveUseCase)
    bulk_assign_category_uc = provide(BulkAssignProductsCategoryUseCase)
    bulk_assign_tags_uc = provide(BulkAssignProductsTagsUseCase)
    bulk_delete_uc = provide(BulkDeleteProductsUseCase)
    bulk_set_tags_active_uc = provide(BulkSetTagsActiveUseCase)
    bulk_delete_tags_uc = provide(BulkDeleteTagsUseCase)

    # Facade
    facade = provide(CatalogFacade)
