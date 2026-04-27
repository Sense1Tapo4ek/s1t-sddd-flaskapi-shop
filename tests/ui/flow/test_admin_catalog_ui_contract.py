from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.flow


ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_admin_shell_has_single_catalog_entry_and_account_footer():
    """
    Given the admin shell navigation,
    When the catalog UI is consolidated,
    Then product/category/tag/security notification entries are not separate sidebar items.
    """
    # Arrange / Act
    base = _read("static/templates/admin/base.html")

    # Assert
    assert 'href="/admin/catalog/"' in base
    assert 'href="/admin/products/"' not in base
    assert 'href="/admin/categories/"' not in base
    assert 'href="/admin/tags/"' not in base
    assert ">Оповещения<" not in base
    assert ">Безопасность<" not in base
    assert 'href="/admin/account"' in base


def test_catalog_workspace_replaces_order_column_with_header_sorting_contract():
    """
    Given the new catalog workspace template and JavaScript,
    When products are rendered inside a selected category,
    Then ordering is table-header sorting only and no product swap UI remains.
    """
    # Arrange / Act
    template = _read("src/catalog/templates/catalog/pages/catalog.html")
    script = _read("static/js/catalog-workspace.js")

    # Assert
    assert "catalog-workspace" in template
    assert "categoryProductsTable" in script
    assert "staticFilters" in script
    assert "sortable: true" in script
    assert "Порядок" not in script
    assert "swapProducts" not in script
    assert "/catalog/admin/swap" not in script


def test_catalog_tree_and_category_editor_have_real_controls():
    """
    Given the consolidated catalog workspace,
    When categories are managed,
    Then tree navigation and category creation/move use first-class UI controls.
    """
    # Arrange / Act
    template = _read("src/catalog/templates/catalog/pages/catalog.html")
    workspace = _read("static/js/catalog-workspace.js")
    tree = _read("static/js/taxonomy-tree.js")

    # Assert
    assert "categoryModal" in template
    assert "category-parent" in template
    assert "window.prompt" not in workspace
    assert "openCategoryForm" in workspace
    assert "populateCategoryParentSelect" in workspace
    assert "data-taxonomy-toggle" in tree
    assert "collapsedIds" in tree
    assert "path" in tree


def test_category_settings_use_single_category_creation_flow():
    """
    Given category settings are inline editing only,
    When a category is selected,
    Then child creation and advanced editing buttons are not rendered there.
    """
    # Arrange / Act
    workspace = _read("static/js/catalog-workspace.js")
    template = _read("src/catalog/templates/catalog/pages/catalog.html")

    # Assert
    assert 'onclick="createRootCategory()">+ Категория</button>' in template
    assert "createChildCategory()" not in workspace
    assert "+ Дочерняя" not in workspace
    assert "Расширенное редактирование" not in workspace


def test_store_settings_expose_template_and_catalog_access_controls():
    """
    Given the store settings page is the template control center,
    When the form is rendered,
    Then it exposes app identity, owner mutation/product permissions, and DB dump controls.
    """
    # Arrange / Act
    form = _read("src/system/templates/system/partials/store_form.html")

    # Assert
    assert 'name="app_name"' in form
    assert 'name="admin_panel_title"' in form
    assert 'name="owner_can_view_category_tree"' not in form
    assert "Просмотр дерева категорий" in form
    assert 'name="owner_can_edit_taxonomy"' in form
    assert 'name="owner_can_view_products"' in form
    assert 'name="owner_can_edit_products"' in form
    assert 'name="owner_can_create_demo_data"' in form
    assert 'href="/admin/settings/database-dump"' in form
    assert "jwt_secret" not in form.lower()
    assert "database_url" not in form.lower()
    assert "root_app_env" not in form.lower()
    assert "cors" not in form.lower()


def test_global_telegram_settings_do_not_store_order_recipient_chat_id():
    """
    Given Telegram chat IDs are per admin account,
    When the global settings form is rendered,
    Then it only saves the bot token and does not expose a global recipient field.
    """
    # Arrange / Act
    form = _read("src/system/templates/system/partials/telegram_form.html")

    # Assert
    assert 'name="bot_token"' in form
    assert 'name="chat_id"' not in form
    assert "/admin/settings/telegram/fetch-chat-id" not in form


def test_branding_save_refreshes_admin_shell_contract():
    """
    Given branding affects sidebar and document title,
    When store settings are saved via HTMX,
    Then the route declares a shell refresh contract.
    """
    # Arrange / Act
    admin = _read("src/system/adapters/driving/admin.py")

    # Assert
    assert 'response.headers["HX-Refresh"] = "true"' in admin


def test_attribute_editor_exposes_only_type_specific_settings():
    """
    Given attributes are always public and filterable,
    When the editor is rendered,
    Then legacy visibility controls and number filter settings are absent.
    """
    # Arrange / Act
    template = _read("src/catalog/templates/catalog/pages/catalog.html")
    workspace = _read("static/js/catalog-workspace.js")

    # Assert
    assert 'option value="color"' not in template
    assert "attribute-filterable" not in template
    assert "attribute-public" not in template
    assert "attribute-number-min" not in template
    assert "attributeFilterPreview" not in template
    assert "attributeValueModeBlock" in template
    assert "attribute-value-mode" in template
    assert "attribute-filterable" not in workspace
    assert "attribute-public" not in workspace
    assert "attribute-number-min" not in workspace
    assert "function isOptionAttributeType" in workspace
    assert "function ensureAttributeOptionPlaceholder" in workspace
    assert "isOptionAttributeType(type)" in workspace


def test_category_products_table_adds_selected_category_attribute_columns():
    """
    Given a category products tab has selected-category attributes,
    When the table is built,
    Then attribute columns are appended and use attr.<code> sort/filter keys.
    """
    # Arrange / Act
    workspace = _read("static/js/catalog-workspace.js")

    # Assert
    assert "buildCategoryProductColumns" in workspace
    assert "`attr.${attr.code}`" in workspace
    assert "schemaEndpoint: '/catalog/admin/search/schema'" in workspace
    assert "loadCategoryProductAttributes" in workspace
    assert "sort_by=attr." not in workspace


def test_category_products_columns_reset_to_selected_category_own_attributes():
    """
    Given products are opened for a selected leaf category,
    When SmartTable is reused after browsing another category,
    Then visible columns reset to base columns plus only the selected category's own attributes.
    """
    # Arrange / Act
    workspace = _read("static/js/catalog-workspace.js")
    smart_table = _read("static/js/smart-table.js")

    # Assert
    assert "state.categoryProductsTableCategoryId" in workspace
    assert "const categoryChanged" in workspace
    assert "data.own || []" in workspace
    assert "preserveVisibility: !categoryChanged" in workspace
    assert "resetInteractionState('created_at', 'desc')" in workspace
    assert "setColumns(columns, { preserveVisibility = true } = {})" in smart_table
    assert "resetInteractionState" in smart_table


def test_smart_table_static_filters_and_sortable_contract():
    """
    Given SmartTable powers catalog products,
    When a column is not sortable or a static category filter is applied,
    Then the UI should not imply unavailable sorting and should expose the active scope.
    """
    # Arrange / Act
    smart_table = _read("static/js/smart-table.js")

    # Assert
    assert "staticFiltersHTML" in smart_table
    assert "filter-chip--static" in smart_table
    assert "c.sortable" in smart_table
    assert "handleSort" in smart_table
    assert "function jsLiteral(value)" in smart_table
    assert "overflow-x:auto" in smart_table


def test_catalog_products_category_and_tags_columns_are_sortable():
    """
    Given products are browsed inside the catalog workspace,
    When users scan by taxonomy fields,
    Then category and tags columns should use the same header sorting contract.
    """
    # Arrange / Act
    workspace = _read("static/js/catalog-workspace.js")

    # Assert
    assert "{ key: 'category', label: 'Категория', sortable: true" in workspace
    assert "{ key: 'tags', label: 'Теги', sortable: true" in workspace


def test_catalog_workspace_uses_initial_category_from_return_url():
    """
    Given a product form returns to the catalog with category_id,
    When the catalog workspace starts,
    Then the tree selects that category and static filter chips show readable scope.
    """
    # Arrange / Act
    workspace = _read("static/js/catalog-workspace.js")

    # Assert
    assert "function initialCategoryIdFromLocation()" in workspace
    assert "new URLSearchParams(window.location.search).get('category_id')" in workspace
    assert "window.categoryTree.load(initialCategoryIdFromLocation())" in workspace
    assert "displayVal: categoryPath(state.selectedCategory)" in workspace
    assert "displayVal: 'включены'" in workspace


def test_catalog_workspace_rebinds_tables_and_escapes_inline_handlers():
    """
    Given catalog workspace HTML is regenerated often,
    When tables render actions and media handlers,
    Then table instances target the current DOM and inline handlers use JS literals.
    """
    # Arrange / Act
    workspace = _read("static/js/catalog-workspace.js")

    # Assert
    assert "state.categoryProductsTable.container = document.getElementById('categoryProducts')" in workspace
    assert "function jsLiteral(value)" in workspace
    assert "openLightbox(${jsLiteral(p.images[0])})" in workspace
    assert "deleteProduct(${Number(p.id)}, ${jsLiteral(p.title)})" in workspace
    assert "openTagForm(${jsLiteral(t)})" in workspace
    assert "openLightbox('${esc" not in workspace
    assert "deleteProduct(${p.id}, '${esc(p.title)}')" not in workspace


def test_catalog_products_view_does_not_autoselect_first_category_without_context():
    """
    Given the legacy products URL redirects to the catalog products view,
    When no category_id is present,
    Then the workspace should not silently filter by the first category.
    """
    # Arrange / Act
    workspace = _read("static/js/catalog-workspace.js")

    # Assert
    assert "function shouldAutoSelectCategory()" in workspace
    assert "initialView() === 'products' && !initialCategoryIdFromLocation()" in workspace
    assert "selectFirst: shouldAutoSelectCategory()" in workspace


def test_admin_catalog_and_account_routes_are_registered(monkeypatch, tmp_path):
    """
    Given the Flask app factory,
    When admin routes are registered,
    Then the consolidated catalog and account pages are routable.
    """
    # Arrange
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

    from root.entrypoints.api import create_app

    # Act
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    # Assert
    assert "/admin/catalog/" in rules
    assert "/admin/account" in rules


def test_catalog_and_account_templates_render(monkeypatch, tmp_path):
    """
    Given the new admin templates,
    When they are rendered inside authenticated request contexts,
    Then their Jinja dependencies are satisfied.
    """
    # Arrange
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

    from flask import render_template, request
    from root.entrypoints.api import create_app

    app = create_app()

    # Act / Assert
    with app.test_request_context("/admin/catalog/"):
        request.admin_payload = {
            "sub": 1,
            "login": "superadmin",
            "role": "superadmin",
            "permissions": {},
        }
        rendered = render_template("catalog/pages/catalog.html")
        assert 'class="catalog-workspace"' in rendered

    with app.test_request_context("/admin/account"):
        request.admin_payload = {
            "sub": 1,
            "login": "owner",
            "role": "owner",
            "permissions": {},
        }
        user = type(
            "UserStub",
            (),
            {"login": "owner", "role": "owner", "telegram_chat_id": None},
        )()
        rendered = render_template("system/pages/account.html", current_user=user)
        assert "Telegram для входа" in rendered


def test_account_password_form_has_client_side_confirmation_contract(monkeypatch, tmp_path):
    """
    Given the account password form,
    When a user changes password,
    Then confirmation stays client-only and mismatch blocks HTMX submission.
    """
    # Arrange
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

    from flask import render_template, request
    from root.entrypoints.api import create_app

    app = create_app()

    # Act
    with app.test_request_context("/admin/account"):
        request.admin_payload = {
            "sub": 1,
            "login": "owner",
            "role": "owner",
            "permissions": {},
        }
        user = type(
            "UserStub",
            (),
            {"login": "owner", "role": "owner", "telegram_chat_id": None},
        )()
        rendered = render_template("system/pages/account.html", current_user=user)

    # Assert
    assert 'id="new_password_confirm"' in rendered
    assert 'name="new_password_confirm"' not in rendered
    assert 'name="old_password"' in rendered
    assert 'name="confirmation_code"' in rendered
    assert 'name="new_password"' in rendered
    assert "validatePasswordForm" in rendered
    assert "preventDefault" in rendered
    assert "password-strength" in rendered
    assert "password-match-status" in rendered
    assert "passwordChanged" in rendered
    assert "form.reset()" in rendered


def test_login_recovery_ttl_comes_from_access_config(monkeypatch, tmp_path):
    """
    Given AccessConfig recovery TTL is configurable,
    When login and recovery partials are rendered,
    Then the Telegram code hint uses configured TTL instead of hard-coded 5 minutes.
    """
    # Arrange
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    monkeypatch.setenv("ACCESS_RECOVERY_CODE_TTL_MINUTES", "17")

    from flask import render_template
    from root.entrypoints.api import create_app

    app = create_app()

    # Act
    login_response = app.test_client().get("/admin/login")
    with app.app_context():
        partial = render_template(
            "access/partials/recovery_code_form.html",
            login="owner",
            remember_me=False,
            recovery_code_ttl_minutes=17,
        )

    # Assert
    rendered_login = login_response.get_data(as_text=True)
    assert login_response.status_code == 200
    assert "17 мин." in rendered_login
    assert "17 мин." in partial
    assert "Код действителен 5 минут" not in rendered_login


def test_telegram_login_errors_swap_into_visible_recovery_section():
    """
    Given Telegram login code request can fail,
    When the route renders an error fragment,
    Then it should be swapped into the visible recovery section instead of hidden login errors.
    """
    # Arrange / Act
    admin = _read("src/access/adapters/driving/admin.py")
    login = _read("src/access/templates/access/pages/login.html")

    # Assert
    assert 'hx-target="#recovery-section"' in login
    assert 'style="color:var(--color-danger);">{msg}</p>' in admin
    assert "), 400" not in admin
    assert "ttl_minutes=config.recovery_code_ttl_minutes" in admin
