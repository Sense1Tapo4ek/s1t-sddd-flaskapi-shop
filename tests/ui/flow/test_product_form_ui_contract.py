from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.flow


ROOT = Path(__file__).resolve().parents[3]


def _read_product_form() -> str:
    return (ROOT / "src/catalog/templates/catalog/pages/product_form.html").read_text(
        encoding="utf-8"
    )


def _section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_existing_image_edit_uploads_new_image_before_deleting_old_image():
    """
    Given an existing product image edited in the browser,
    When the user applies the edit,
    Then the new blob is uploaded before the old image delete request is sent.
    """
    # Arrange / Act
    source = _read_product_form()
    edit_body = _section(source, "async function editExistingImage", "async function deleteImage")

    # Assert
    upload_call = "const uploadRes = await api.put('/catalog/' + productId, fd);"
    delete_call = "const deleteRes = await api.del('/catalog/' + productId + '/images'"
    assert upload_call in edit_body
    assert delete_call in edit_body
    assert edit_body.index(upload_call) < edit_body.index(delete_call)
    assert "method: 'DELETE'" not in edit_body
    assert "Новое фото загружено, но старое не удалилось" in edit_body
    assert "loadProduct();" in edit_body


def test_new_image_preview_items_can_be_removed_before_submit():
    """
    Given selected or edited images staged in the product form,
    When a user removes a preview thumbnail,
    Then the matching blob is removed from editedImages before submit.
    """
    # Arrange / Act
    source = _read_product_form()

    # Assert
    assert "function removeEditedImage(id)" in source
    assert "editedImages = editedImages.filter(image => image.id !== id);" in source
    assert "URL.revokeObjectURL(item.url);" in source
    assert 'onclick="removeEditedImage(${id})"' in source
    assert "fd.append(fieldName, image.blob, 'edited.jpg');" in source


def test_product_form_returns_to_catalog_products_with_initial_category_context():
    """
    Given a product form opened from a category,
    When the user cancels or successfully creates a product,
    Then the catalog return URL preserves category_id for the workspace.
    """
    # Arrange / Act
    source = _read_product_form()

    # Assert
    assert "/admin/catalog/?view=products&category_id={{ initial_category_id }}" in source
    assert "const catalogReturnUrl = '/admin/catalog/?view=products' + (" in source
    assert "'&category_id=' + encodeURIComponent(initialCategoryId)" in source
    assert "window.location = catalogReturnUrl;" in source


def test_product_form_reuses_taxonomy_controls_after_reload():
    """
    Given editing a product reloads its data after save,
    When taxonomy controls are initialized again,
    Then existing widgets are reused instead of stacking duplicate DOM listeners.
    """
    # Arrange / Act
    source = _read_product_form()

    # Assert
    assert "if (!categorySelect)" in source
    assert "if (!tagPicker)" in source
    assert "if (!attributeForm)" in source
    assert "categorySelect.selectedId = categoryId ? Number(categoryId) : null;" in source


def test_product_form_image_handlers_use_js_literals():
    """
    Given image paths can contain quotes or special characters,
    When current image actions are rendered,
    Then handlers pass paths as JS literals instead of quoted HTML-escaped strings.
    """
    # Arrange / Act
    source = _read_product_form()

    # Assert
    assert "function jsLiteral(value)" in source
    assert "editExistingImage(${jsLiteral(src)})" in source
    assert "deleteImage(this, ${jsLiteral(src)})" in source
    assert "editExistingImage('${esc(src)}')" not in source
    assert "deleteImage(this, '${esc(src)}')" not in source


def test_product_form_template_renders_cancel_url_with_initial_category(
    monkeypatch, tmp_path
):
    """
    Given the new product form opened from a catalog category,
    When the template is rendered,
    Then the cancel link keeps the category context in the catalog URL.
    """
    # Arrange
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

    from flask import render_template, request
    from root.entrypoints.api import create_app

    app = create_app()

    # Act
    with app.test_request_context("/admin/products/new?category_id=42"):
        request.admin_payload = {
            "sub": 1,
            "login": "superadmin",
            "role": "superadmin",
            "permissions": {},
        }
        rendered = render_template(
            "catalog/pages/product_form.html",
            product_id=None,
            initial_category_id=42,
        )

    # Assert
    assert 'href="/admin/catalog/?view=products&category_id=42"' in rendered
    assert "const initialCategoryId = 42;" in rendered


def test_product_edit_route_accepts_category_return_context():
    """
    Given a product edit form is opened from a category products table,
    When the edit route renders the form,
    Then it forwards category_id into the shared return URL contract.
    """
    # Arrange / Act
    admin = (ROOT / "src/catalog/adapters/driving/admin.py").read_text(encoding="utf-8")
    workspace = (ROOT / "static/js/catalog-workspace.js").read_text(encoding="utf-8")

    # Assert
    assert "parse_optional_int(request.args.get(\"category_id\"), \"category_id\")" in admin
    assert "initial_category_id=category_id" in admin
    assert "/admin/products/${p.id}/edit?category_id=${state.selectedCategoryId || ''}" in workspace
