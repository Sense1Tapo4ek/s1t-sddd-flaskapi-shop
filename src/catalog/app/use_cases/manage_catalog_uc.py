from dataclasses import dataclass
from shared.generics.pagination import PaginatedResult, PaginationParams
from ...domain import Product, ProductNotFoundError
from ..interfaces import IProductRepo, IFileStorage


@dataclass(frozen=True, slots=True, kw_only=True)
class ManageCatalogUseCase:
    """
    Admin access to the catalog (Write + Search).
    """

    _repo: IProductRepo
    _storage: IFileStorage

    def search(
        self,
        query: str,
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        filters: dict | None = None,
    ) -> PaginatedResult[Product]:

        params = PaginationParams(
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=filters or {},
        )

        return self._repo.search(query, params)

    def create(
        self,
        title: str,
        price: float,
        description: str,
        images: list[tuple[str, bytes]],
    ) -> Product:
        # 1. Save images
        image_paths = []
        for filename, data in images:
            path = self._storage.save(filename, data)
            image_paths.append(path)

        # 2. Create Domain Object (ID=0, repo will assign)
        product = Product.create(
            id=0, title=title, price=price, description=description, images=image_paths
        )

        # 3. Persist
        return self._repo.create(product)

    def update(
        self,
        product_id: int,
        title: str | None = None,
        price: float | None = None,
        description: str | None = None,
        new_images: list[tuple[str, bytes]] | None = None,
        deleted_images: list[str] | None = None,
    ) -> Product:
        # 1. Load
        product = self._repo.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)

        # 2. Handle Image Side Effects (Infra)
        if deleted_images:
            for path in deleted_images:
                self._storage.delete(path)
                if path in product.images:
                    product.images.remove(path)

        if new_images:
            for filename, data in new_images:
                path = self._storage.save(filename, data)
                product.images.append(path)

        # 3. Update Domain Fields
        if title is not None:
            product.title = title
        if price is not None:
            product.price = price
        if description is not None:
            product.description = description

        # 4. Persist
        return self._repo.update(product)

    def delete_image(self, product_id: int, image_path: str) -> Product:
        product = self._repo.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)

        if image_path not in product.images:
            raise ProductNotFoundError(product_id)

        self._storage.delete(image_path)
        product.images.remove(image_path)
        return self._repo.update(product)

    def delete(self, product_id: int) -> bool:
        # 1. Load to clean up files
        product = self._repo.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)

        # 2. Clean up files
        for path in product.images:
            self._storage.delete(path)

        # 3. Delete from DB
        return self._repo.delete(product_id)

    def swap_ids(self, id_a: int, id_b: int) -> None:
        self._repo.swap_ids(id_a, id_b)
