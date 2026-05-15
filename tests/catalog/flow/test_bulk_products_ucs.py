"""Flow tests for products-bulk use cases.

Mocks IProductRepo and (where applicable) ITaxonomyRepo. Verifies:
- Each per-id call reaches the repo.
- DomainError / ApplicationError from the repo becomes a BulkFailure row.
- Setup validation (missing category, missing tag, invalid mode) short-circuits
  before the bulk loop runs.
"""
from __future__ import annotations

from unittest.mock import create_autospec

import pytest

from catalog.app.interfaces import IProductRepo, ITaxonomyRepo
from catalog.app.use_cases import (
    BulkAssignProductsCategoryCommand,
    BulkAssignProductsCategoryUseCase,
    BulkAssignProductsTagsCommand,
    BulkAssignProductsTagsUseCase,
    BulkDeleteProductsCommand,
    BulkDeleteProductsUseCase,
    BulkSetProductsActiveCommand,
    BulkSetProductsActiveUseCase,
)
from catalog.domain import (
    Category,
    CategoryNotFoundError,
    InvalidBulkTagModeError,
    InvalidProductError,
    ProductInUseByActiveOrderError,
    ProductNotFoundError,
    Tag,
    TagNotFoundError,
)
from shared.ports.driving.bulk_schemas import BulkTargetFilter, BulkTargetIds

pytestmark = pytest.mark.flow


def _ids(*xs: int) -> BulkTargetIds:
    return BulkTargetIds(ids=list(xs))


def _category(category_id: int = 5) -> Category:
    return Category(
        id=category_id,
        title="cat",
        slug="cat",
        description="",
        sort_order=0,
        is_active=True,
        parent_id=None,
    )


def _tag(tag_id: int) -> Tag:
    from datetime import datetime

    return Tag(
        id=tag_id,
        title=f"t{tag_id}",
        slug=f"t{tag_id}",
        color="#000",
        sort_order=0,
        is_active=True,
        created_at=datetime.now(),
    )


# ─── BulkSetProductsActiveUseCase ───────────────────────────────────


class TestBulkSetProductsActive:
    def test_ids_mode_happy_path(self):
        """
        Given 3 product ids,
        When the UC runs in ids-mode with active=True,
        Then repo.set_active is called once per id and ok=3.
        """
        repo = create_autospec(IProductRepo, instance=True)
        uc = BulkSetProductsActiveUseCase(_repo=repo)

        result = uc(BulkSetProductsActiveCommand(target=_ids(1, 2, 3), active=True))

        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []
        assert repo.set_active.call_count == 3
        repo.set_active.assert_any_call(1, True)

    def test_partial_failure_when_one_id_missing(self):
        """
        Given 3 ids and one missing in the repo,
        When the UC runs,
        Then failed contains exactly that id with code "PRODUCT_NOT_FOUND".
        """
        repo = create_autospec(IProductRepo, instance=True)

        def side_effect(pid: int, _active: bool) -> None:
            if pid == 2:
                raise ProductNotFoundError(pid)

        repo.set_active.side_effect = side_effect
        uc = BulkSetProductsActiveUseCase(_repo=repo)

        result = uc(BulkSetProductsActiveCommand(target=_ids(1, 2, 3), active=False))

        assert result.total == 3
        assert result.ok == 2
        assert [f.id for f in result.failed] == [2]
        assert result.failed[0].reason == "PRODUCT_NOT_FOUND"

    def test_filter_mode_iterates_via_cursor(self):
        """
        Given a filter target,
        When iter_ids_by_filter returns two pages,
        Then both pages are processed and total reflects all ids.
        """
        repo = create_autospec(IProductRepo, instance=True)
        repo.iter_ids_by_filter.side_effect = [
            ([10, 11], "11"),
            ([12], None),
        ]
        uc = BulkSetProductsActiveUseCase(_repo=repo)

        result = uc(
            BulkSetProductsActiveCommand(
                target=BulkTargetFilter(filter={"q": "x"}),
                active=True,
            )
        )

        assert result.total == 3
        assert result.ok == 3
        assert repo.set_active.call_count == 3


# ─── BulkAssignProductsCategoryUseCase ──────────────────────────────


class TestBulkAssignProductsCategory:
    def test_happy_path(self):
        repo = create_autospec(IProductRepo, instance=True)
        tax = create_autospec(ITaxonomyRepo, instance=True)
        tax.get_category.return_value = _category(5)
        tax.is_leaf_category.return_value = True
        uc = BulkAssignProductsCategoryUseCase(_repo=repo, _taxonomy_repo=tax)

        result = uc(
            BulkAssignProductsCategoryCommand(target=_ids(1, 2), category_id=5)
        )

        assert result.ok == 2
        assert repo.assign_category.call_count == 2
        repo.assign_category.assert_any_call(2, 5)

    def test_rejects_missing_category_before_loop(self):
        repo = create_autospec(IProductRepo, instance=True)
        tax = create_autospec(ITaxonomyRepo, instance=True)
        tax.get_category.return_value = None
        uc = BulkAssignProductsCategoryUseCase(_repo=repo, _taxonomy_repo=tax)

        with pytest.raises(CategoryNotFoundError):
            uc(BulkAssignProductsCategoryCommand(target=_ids(1, 2), category_id=99))

        repo.assign_category.assert_not_called()

    def test_rejects_non_leaf_category(self):
        repo = create_autospec(IProductRepo, instance=True)
        tax = create_autospec(ITaxonomyRepo, instance=True)
        tax.get_category.return_value = _category(5)
        tax.is_leaf_category.return_value = False
        uc = BulkAssignProductsCategoryUseCase(_repo=repo, _taxonomy_repo=tax)

        with pytest.raises(InvalidProductError):
            uc(BulkAssignProductsCategoryCommand(target=_ids(1), category_id=5))

        repo.assign_category.assert_not_called()


# ─── BulkAssignProductsTagsUseCase ──────────────────────────────────


class TestBulkAssignProductsTags:
    def test_happy_path_replace_mode(self):
        repo = create_autospec(IProductRepo, instance=True)
        tax = create_autospec(ITaxonomyRepo, instance=True)
        tax.get_tag.side_effect = lambda tag_id: _tag(tag_id)
        uc = BulkAssignProductsTagsUseCase(_repo=repo, _taxonomy_repo=tax)

        result = uc(
            BulkAssignProductsTagsCommand(
                target=_ids(10, 11),
                tag_ids=[1, 2],
                mode="replace",
            )
        )

        assert result.ok == 2
        repo.apply_tags.assert_any_call(10, [1, 2], "replace")
        repo.apply_tags.assert_any_call(11, [1, 2], "replace")

    def test_rejects_invalid_mode(self):
        repo = create_autospec(IProductRepo, instance=True)
        tax = create_autospec(ITaxonomyRepo, instance=True)
        uc = BulkAssignProductsTagsUseCase(_repo=repo, _taxonomy_repo=tax)

        with pytest.raises(InvalidBulkTagModeError):
            uc(
                BulkAssignProductsTagsCommand(
                    target=_ids(1), tag_ids=[1], mode="merge",  # type: ignore[arg-type]
                )
            )
        repo.apply_tags.assert_not_called()

    def test_rejects_missing_tag(self):
        repo = create_autospec(IProductRepo, instance=True)
        tax = create_autospec(ITaxonomyRepo, instance=True)
        tax.get_tag.return_value = None
        uc = BulkAssignProductsTagsUseCase(_repo=repo, _taxonomy_repo=tax)

        with pytest.raises(TagNotFoundError):
            uc(
                BulkAssignProductsTagsCommand(
                    target=_ids(1), tag_ids=[42], mode="add",
                )
            )
        repo.apply_tags.assert_not_called()


# ─── BulkDeleteProductsUseCase ──────────────────────────────────────


class TestBulkDeleteProducts:
    def test_happy_path(self):
        repo = create_autospec(IProductRepo, instance=True)
        uc = BulkDeleteProductsUseCase(_repo=repo)

        result = uc(BulkDeleteProductsCommand(target=_ids(1, 2, 3)))

        assert result.ok == 3
        assert result.failed == []
        assert repo.bulk_delete_one.call_count == 3

    def test_partial_failure_when_product_in_active_order(self):
        """
        Given a product that raises ProductInUseByActiveOrderError,
        When the UC runs,
        Then that id appears in failed[] with the matching reason code.
        """
        repo = create_autospec(IProductRepo, instance=True)

        def side_effect(pid: int) -> None:
            if pid == 7:
                raise ProductInUseByActiveOrderError(pid)

        repo.bulk_delete_one.side_effect = side_effect
        uc = BulkDeleteProductsUseCase(_repo=repo)

        result = uc(BulkDeleteProductsCommand(target=_ids(5, 7, 9)))

        assert result.ok == 2
        assert [f.id for f in result.failed] == [7]
        assert result.failed[0].reason == "product_in_use_by_active_order"
