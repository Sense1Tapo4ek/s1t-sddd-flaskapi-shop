(function() {
  'use strict';

  const perms = window.catalogPermissions || {};
  const state = {
    selectedCategoryId: null,
    selectedCategory: null,
    productsIncludeDescendants: false,
    categoryProductAttributes: [],
    categoryProductsTable: null,
    categoryProductsTableCategoryId: null,
    tagsTable: null,
    editingCategory: null,
    editingAttribute: null,
    editingTagId: null
  };

  function showToast(message, type) {
    document.body.dispatchEvent(new CustomEvent('showToast', {
      detail: { message, type: type || 'info' }
    }));
  }

  function categoryIsLeaf(category) {
    return !(category.children && category.children.length);
  }

  function categoryPath(category) {
    if (!category || !category.path) return category ? category.title : '';
    return category.path.join(' / ');
  }

  function jsLiteral(value) {
    return esc(JSON.stringify(value == null ? '' : value));
  }

  function initialView() {
    return document.querySelector('.catalog-workspace')?.dataset.initialView || 'tree';
  }

  function initialCategoryIdFromLocation() {
    const raw = new URLSearchParams(window.location.search).get('category_id');
    const id = Number(raw);
    return Number.isFinite(id) && id > 0 ? id : null;
  }

  function shouldAutoSelectCategory() {
    return !(initialView() === 'products' && !initialCategoryIdFromLocation());
  }

  function boolChecked(value) {
    return value ? 'checked' : '';
  }

  function detailPanel() {
    return document.getElementById('catalogDetailPanel');
  }

  function renderCategoryWorkspace(category) {
    state.selectedCategory = category;
    state.selectedCategoryId = category.id;
    state.productsIncludeDescendants = !categoryIsLeaf(category);
    const leafLabel = categoryIsLeaf(category) ? 'конечная категория' : 'группа';
    const productsTab = perms.canViewProducts
      ? '<button class="tab-btn" type="button" onclick="openCatalogTab(\'products\', this); loadCategoryProducts()">Товары</button>'
      : '';

    detailPanel().innerHTML = `
      <div class="catalog-category-head">
        <div>
          <div class="catalog-category-head__path">${esc(categoryPath(category))}</div>
          <h3 class="catalog-category-head__title">${esc(category.title)}</h3>
          <div class="catalog-category-head__meta">/${esc(category.slug)} · ${leafLabel} · ${category.product_count || 0} товаров</div>
        </div>
        <span class="taxonomy-status ${category.is_active ? '' : 'taxonomy-status--inactive'}">${category.is_active ? 'Активна' : 'Скрыта'}</span>
      </div>

      <div class="tabs catalog-tabs">
        <button class="tab-btn tab-btn--active" type="button" onclick="openCatalogTab('settings', this)">Настройки</button>
        <button class="tab-btn" type="button" onclick="openCatalogTab('attributes', this); loadAttributes()">Атрибуты</button>
        ${productsTab}
      </div>

      <section id="tab-settings" class="tab-panel tab-panel--active">
        ${renderCategorySettings(category)}
      </section>

      <section id="tab-attributes" class="tab-panel">
        <div id="attributesContainer" class="taxonomy-empty">Загрузка атрибутов...</div>
      </section>

      ${perms.canViewProducts ? `
        <section id="tab-products" class="tab-panel">
          <div class="catalog-table-toolbar">
            <div class="taxonomy-toggle">
              <button class="taxonomy-toggle__btn ${state.productsIncludeDescendants ? '' : 'taxonomy-toggle__btn--active'}" id="catProductsDirect" type="button" onclick="setProductsMode(false)">Только эта</button>
              <button class="taxonomy-toggle__btn ${state.productsIncludeDescendants ? 'taxonomy-toggle__btn--active' : ''}" id="catProductsDesc" type="button" onclick="setProductsMode(true)">С подкатегориями</button>
            </div>
            ${perms.canEditProducts ? `<a class="btn btn--primary btn--sm" href="/admin/products/new?category_id=${category.id}">+ Новый товар</a>` : ''}
          </div>
          <div id="categoryProducts"></div>
        </section>
      ` : ''}
    `;
    populateCategoryParentSelect(
      document.getElementById('category-parent-inline'),
      category.parent_id,
      excludedCategoryIds(category)
    );

    if (perms.canViewProducts) {
      if (initialView() === 'products') {
        const btn = detailPanel().querySelector('[onclick*="products"]');
        window.openCatalogTab('products', btn);
        window.loadCategoryProducts();
      }
    }
  }

  function renderCategorySettings(category) {
    const readonly = !perms.canEditTaxonomy;
    return `
      <form id="categoryForm" class="form form--wide catalog-settings-form" onsubmit="saveCategory(event)">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Название</label>
            <input class="form-input" name="title" value="${esc(category.title)}" required ${readonly ? 'disabled' : ''}>
          </div>
          <div class="form-group">
            <label class="form-label">Slug</label>
            <input class="form-input" name="slug" value="${esc(category.slug)}" ${readonly ? 'disabled' : ''}>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Описание</label>
          <textarea class="form-input form-textarea" name="description" ${readonly ? 'disabled' : ''}>${esc(category.description || '')}</textarea>
        </div>
        <div class="form-group">
          <label class="form-label" for="category-parent-inline">Родитель</label>
          <select class="form-input" id="category-parent-inline" name="parent_id" ${readonly ? 'disabled' : ''}></select>
        </div>
        <label class="catalog-checkbox">
          <input type="checkbox" name="is_active" ${boolChecked(category.is_active)} ${readonly ? 'disabled' : ''}>
          <span>Активна</span>
        </label>
        ${readonly ? '<p class="taxonomy-muted">Режим только для чтения.</p>' : `
          <div class="form-actions">
            <button class="btn btn--primary" type="submit">Сохранить</button>
            <button class="btn btn--danger" type="button" onclick="deleteSelectedCategory()">Удалить</button>
          </div>
        `}
      </form>
    `;
  }

  window.openCatalogTab = function(name, btn) {
    detailPanel().querySelectorAll('.tab-btn').forEach(el => el.classList.remove('tab-btn--active'));
    if (btn) btn.classList.add('tab-btn--active');
    detailPanel().querySelectorAll('.tab-panel').forEach(el => el.classList.remove('tab-panel--active'));
    const panel = document.getElementById('tab-' + name);
    if (panel) panel.classList.add('tab-panel--active');
  };

  window.reloadCatalogTree = function(preferredId) {
    return window.categoryTree.load(preferredId || state.selectedCategoryId);
  };

  window.selectedCategory = function() {
    return state.selectedCategory;
  };

  window.filterCategoryTree = function(rawTerm) {
    const term = String(rawTerm || '').trim().toLowerCase();
    document.querySelectorAll('#categoryTree .taxonomy-tree__item').forEach(item => {
      item.hidden = Boolean(term) && !item.innerText.toLowerCase().includes(term);
    });
  };

  function excludedCategoryIds(category) {
    if (!category) return new Set();
    const ids = new Set([Number(category.id)]);
    if (window.TaxonomyApi && window.TaxonomyApi.descendantIds) {
      window.TaxonomyApi.descendantIds(category).forEach(id => ids.add(Number(id)));
    }
    return ids;
  }

  function categoryOptions(selectedParentId, excludeIds) {
    const flat = window.TaxonomyApi
      ? window.TaxonomyApi.flattenTree(window.categoryTree.tree || [])
      : [];
    const options = ['<option value="">Корень каталога</option>'];
    flat.forEach(category => {
      if (excludeIds && excludeIds.has(Number(category.id))) return;
      const label = `${'— '.repeat(category.depth || 0)}${category.path ? category.path.join(' / ') : category.title}`;
      options.push(
        `<option value="${category.id}" ${Number(selectedParentId) === Number(category.id) ? 'selected' : ''}>${esc(label)}</option>`
      );
    });
    return options.join('');
  }

  window.populateCategoryParentSelect = populateCategoryParentSelect;
  function populateCategoryParentSelect(selectEl, selectedParentId, excludeIds) {
    if (!selectEl) return;
    selectEl.innerHTML = categoryOptions(selectedParentId, excludeIds || new Set());
  }

  window.openCategoryForm = function(category, parentId) {
    if (!perms.canEditTaxonomy) return;
    state.editingCategory = category || null;
    document.getElementById('categoryModalTitle').textContent = category ? 'Редактировать категорию' : 'Новая категория';
    document.getElementById('category-id').value = category ? category.id : '';
    document.getElementById('category-title').value = category ? category.title : '';
    document.getElementById('category-slug').value = category ? category.slug : '';
    document.getElementById('category-description').value = category ? (category.description || '') : '';
    document.getElementById('category-active').checked = category ? category.is_active : true;
    populateCategoryParentSelect(
      document.getElementById('category-parent'),
      category ? category.parent_id : parentId,
      excludedCategoryIds(category)
    );
    document.getElementById('categoryModal').classList.add('modal-overlay--active');
  };

  window.closeCategoryForm = function() {
    document.getElementById('categoryModal').classList.remove('modal-overlay--active');
  };

  window.createRootCategory = function() {
    window.openCategoryForm(null, null);
  };

  window.saveCategoryModal = async function(event) {
    event.preventDefault();
    if (!perms.canEditTaxonomy) return;
    const id = document.getElementById('category-id').value;
    const parentRaw = document.getElementById('category-parent').value;
    const payload = {
      title: document.getElementById('category-title').value,
      slug: document.getElementById('category-slug').value || null,
      description: document.getElementById('category-description').value,
      parent_id: parentRaw ? Number(parentRaw) : null,
      is_active: document.getElementById('category-active').checked
    };
    const res = id
      ? await api.put('/catalog/admin/categories/' + id, payload)
      : await api.post('/catalog/admin/categories', payload);
    if (res._failed) return;
    window.closeCategoryForm();
    showToast(id ? 'Категория сохранена' : 'Категория создана', 'success');
    await window.reloadCatalogTree(res.id);
  };

  window.saveCategory = async function(event) {
    event.preventDefault();
    if (!perms.canEditTaxonomy || !state.selectedCategoryId) return;
    const form = new FormData(event.target);
    const payload = {
      title: form.get('title'),
      slug: form.get('slug'),
      description: form.get('description'),
      parent_id: form.get('parent_id') ? Number(form.get('parent_id')) : null,
      is_active: Boolean(form.get('is_active'))
    };
    const res = await api.put('/catalog/admin/categories/' + state.selectedCategoryId, payload);
    if (res._failed) return;
    showToast('Категория сохранена', 'success');
    await window.reloadCatalogTree(res.id);
  };

  window.deleteSelectedCategory = async function() {
    if (!perms.canEditTaxonomy || !state.selectedCategoryId) return;
    const confirmed = await confirmDanger('Удалить категорию?', 'Категория будет удалена, если в ней нет дочерних категорий и товаров.');
    if (!confirmed) return;
    const res = await api.del('/catalog/admin/categories/' + state.selectedCategoryId);
    if (res._failed) return;
    state.selectedCategoryId = null;
    showToast('Категория удалена', 'success');
    detailPanel().innerHTML = '<div class="catalog-empty"><div class="catalog-empty__title">Выберите категорию</div><div class="catalog-empty__text">Слева находится дерево каталога.</div></div>';
    await window.reloadCatalogTree();
  };

  function confirmDanger(title, text) {
    return Promise.resolve(window.confirm(title + '\n' + text));
  }

  window.loadAttributes = async function() {
    if (!state.selectedCategoryId) return;
    const data = await api.get(`/catalog/admin/categories/${state.selectedCategoryId}/attributes`);
    if (data._failed) return;
    renderAttributes(data);
  };

  function attributeSummary(attr) {
    const parts = [attr.code, attr.type];
    if (attr.unit) parts.push(attr.unit);
    if (attr.is_required) parts.push('обязательный');
    if (['file', 'image'].includes(attr.type)) {
      parts.push(attr.value_mode === 'multiple' ? 'несколько значений' : 'одно значение');
    }
    return parts.join(' · ');
  }

  function renderAttributes(data) {
    const inherited = (data.inherited || []).map(attr => `
      <article class="taxonomy-card">
        <div class="taxonomy-card__title">${esc(attr.title)}</div>
        <div class="taxonomy-editor__meta">${esc(attributeSummary(attr))}</div>
        <div class="taxonomy-editor__meta">Наследуется от ${esc(attr.inherited_from_title || '')}</div>
      </article>
    `).join('');
    const own = (data.own || []).map(attr => `
      <article class="taxonomy-card">
        <div class="taxonomy-card__title">${esc(attr.title)}</div>
        <div class="taxonomy-editor__meta">${esc(attributeSummary(attr))}</div>
        ${renderAttributeOptions(attr)}
        ${perms.canEditTaxonomy ? `
          <div class="catalog-card-actions">
            <button class="btn btn--ghost btn--sm" type="button" onclick="openAttributeForm(${jsLiteral(attr)})">Изм.</button>
            <button class="btn btn--danger btn--sm" type="button" onclick="deleteAttribute(${attr.id})">Удалить</button>
          </div>
        ` : ''}
      </article>
    `).join('');
    document.getElementById('attributesContainer').innerHTML = `
      <div class="catalog-table-toolbar">
        <div>
          <div class="catalog-section-title">Атрибуты категории</div>
          <div class="catalog-section-hint">Наследуемые читаются сверху, собственные можно редактировать здесь.</div>
        </div>
        ${perms.canEditTaxonomy ? '<button class="btn btn--primary btn--sm" type="button" onclick="openAttributeForm()">+ Атрибут</button>' : ''}
      </div>
      <div class="catalog-subtitle">Наследуемые</div>
      <div class="taxonomy-grid">${inherited || '<p class="empty-text">Нет наследуемых атрибутов</p>'}</div>
      <div class="catalog-subtitle">Свои</div>
      <div class="taxonomy-grid">${own || '<p class="empty-text">Нет собственных атрибутов</p>'}</div>
    `;
  }

  function renderAttributeOptions(attr) {
    const visibleOptions = (attr.options || []).filter(option => !String(option.value || '').startsWith('__'));
    if (!visibleOptions.length) return '';
    return `
      <div class="catalog-option-list">
        ${visibleOptions.map(option => `<span>${esc(option.label)}</span>`).join('')}
      </div>
    `;
  }

  window.openAttributeForm = function(attr) {
    state.editingAttribute = attr || null;
    document.getElementById('attributeModalTitle').textContent = attr ? 'Редактировать атрибут' : 'Новый атрибут';
    document.getElementById('attribute-id').value = attr ? attr.id : '';
    document.getElementById('attribute-title').value = attr ? attr.title : '';
    document.getElementById('attribute-code').value = attr ? attr.code : '';
    document.getElementById('attribute-type').value = attr ? attr.type : 'text';
    document.getElementById('attribute-unit').value = attr && attr.unit ? attr.unit : '';
    document.getElementById('attribute-required').checked = attr ? attr.is_required : false;
    document.getElementById('attribute-value-mode').value = attr && attr.value_mode ? attr.value_mode : 'single';
    renderAttributeOptionInputs(
      attr && attr.options
        ? attr.options.filter(option => !String(option.value || '').startsWith('__'))
        : []
    );
    window.syncAttributeTypeFields();
    document.getElementById('attributeModal').classList.add('modal-overlay--active');
  };

  window.closeAttributeForm = function() {
    document.getElementById('attributeModal').classList.remove('modal-overlay--active');
  };

  window.syncAttributeTypeFields = function() {
    const type = document.getElementById('attribute-type').value;
    const usesOptions = isOptionAttributeType(type);
    document.getElementById('attributeOptionsBlock').hidden = !usesOptions;
    document.getElementById('attributeUnitBlock').hidden = type !== 'number';
    document.getElementById('attributeValueModeBlock').hidden = !['file', 'image'].includes(type);
    if (usesOptions) ensureAttributeOptionPlaceholder();
  };

  function isOptionAttributeType(type) {
    return ['select', 'multiselect'].includes(type);
  }

  function ensureAttributeOptionPlaceholder() {
    const container = document.getElementById('attributeOptions');
    if (container && !container.children.length) {
      window.addAttributeOption();
    }
  }

  function renderAttributeOptionInputs(options) {
    const container = document.getElementById('attributeOptions');
    container.innerHTML = '';
    (options || []).forEach(option => window.addAttributeOption(option));
  }

  window.addAttributeOption = function(option) {
    const container = document.getElementById('attributeOptions');
    const row = document.createElement('div');
    row.className = 'attribute-options__row';
    row.innerHTML = `
      <input class="form-input form-input--sm" data-option-value placeholder="value" value="${esc(option && option.value ? option.value : '')}">
      <input class="form-input form-input--sm" data-option-label placeholder="label" value="${esc(option && option.label ? option.label : '')}">
      <span class="attribute-options__actions">
        <button class="btn btn--ghost btn--sm" type="button" onclick="moveAttributeOption(this, -1)">↑</button>
        <button class="btn btn--ghost btn--sm" type="button" onclick="moveAttributeOption(this, 1)">↓</button>
        <button class="btn btn--ghost btn--sm" type="button" onclick="this.closest('.attribute-options__row').remove()">Удалить</button>
      </span>
    `;
    container.appendChild(row);
  };

  window.moveAttributeOption = function(button, direction) {
    const row = button.closest('.attribute-options__row');
    if (!row) return;
    if (direction < 0 && row.previousElementSibling) {
      row.parentNode.insertBefore(row, row.previousElementSibling);
    }
    if (direction > 0 && row.nextElementSibling) {
      row.parentNode.insertBefore(row.nextElementSibling, row);
    }
  };

  window.saveAttribute = async function(event) {
    event.preventDefault();
    if (!perms.canEditTaxonomy || !state.selectedCategoryId) return;
    const id = document.getElementById('attribute-id').value;
    const payload = {
      title: document.getElementById('attribute-title').value,
      code: document.getElementById('attribute-code').value,
      type: document.getElementById('attribute-type').value,
      unit: document.getElementById('attribute-type').value === 'number'
        ? document.getElementById('attribute-unit').value || null
        : null,
      is_required: document.getElementById('attribute-required').checked,
      value_mode: ['file', 'image'].includes(document.getElementById('attribute-type').value)
        ? document.getElementById('attribute-value-mode').value
        : 'single',
      options: collectAttributeOptions()
    };
    const res = id
      ? await api.put(`/catalog/admin/categories/${state.selectedCategoryId}/attributes/${id}`, payload)
      : await api.post(`/catalog/admin/categories/${state.selectedCategoryId}/attributes`, payload);
    if (res._failed) return;
    window.closeAttributeForm();
    showToast('Атрибут сохранен', 'success');
    window.loadAttributes();
  };

  function collectAttributeOptions() {
    const type = document.getElementById('attribute-type').value;
    if (!isOptionAttributeType(type)) return [];
    return Array.from(document.querySelectorAll('#attributeOptions .attribute-options__row'))
      .map((row, index) => ({
        value: row.querySelector('[data-option-value]').value,
        label: row.querySelector('[data-option-label]').value,
        sort_order: index
      }))
      .filter(option => option.value && option.label);
  }

  window.deleteAttribute = async function(id) {
    if (!perms.canEditTaxonomy || !state.selectedCategoryId) return;
    if (!window.confirm('Удалить атрибут?')) return;
    const res = await api.del(`/catalog/admin/categories/${state.selectedCategoryId}/attributes/${id}`);
    if (res._failed) return;
    showToast('Атрибут удален', 'success');
    window.loadAttributes();
  };

  function productAttributeMap(product) {
    const map = {};
    (product.attributes || []).forEach(attribute => {
      map[attribute.code] = attribute.value;
    });
    return map;
  }

  function renderAttributeValue(attr, product) {
    const values = productAttributeMap(product);
    let value = values[attr.code];
    if ((value === undefined || value === null || value === '') && attr.type === 'date') {
      value = product.created_at ? String(product.created_at).slice(0, 10) : '';
    }
    if (value === undefined || value === null || value === '' || (Array.isArray(value) && !value.length)) {
      return '-';
    }
    if (attr.type === 'boolean') return value ? 'Да' : 'Нет';
    if (Array.isArray(value)) return value.map(item => esc(item)).join(', ');
    if (attr.type === 'url') return `<a href="${esc(value)}" target="_blank" rel="noopener">${esc(value)}</a>`;
    return esc(value);
  }

  function attributeColumn(attr) {
    return {
      key: `attr.${attr.code}`,
      label: attr.title,
      sortable: true,
      render: product => renderAttributeValue(attr, product)
    };
  }

  function buildCategoryProductColumns(attributes) {
    return [
      { key: 'id', label: '#', sortable: true },
      {
        key: 'image', label: 'Фото', sortable: false,
        render: p => p.images && p.images[0]
          ? `<img src="${esc(p.images[0])}" class="catalog-product-thumb" onclick="openLightbox(${jsLiteral(p.images[0])})">`
          : '<span class="empty-text">-</span>'
      },
      { key: 'title', label: 'Название', sortable: true },
      { key: 'price', label: 'Цена', sortable: true, render: p => parseFloat(p.price || 0).toFixed(2) + ' BYN' },
      { key: 'category', label: 'Категория', sortable: true, render: p => p.category_path && p.category_path.length ? esc(p.category_path.join(' / ')) : (p.category ? esc(p.category.title) : '-') },
      { key: 'tags', label: 'Теги', sortable: true, render: p => (p.tags || []).map(t => `<span class="badge">${esc(t.title)}</span>`).join(' ') || '-' },
      ...attributes.map(attributeColumn),
      { key: 'created_at', label: 'Дата', sortable: true, render: p => p.created_at ? String(p.created_at).slice(0, 10) : '-' },
      {
        key: 'actions', label: 'Действия', sortable: false,
        render: p => perms.canEditProducts
          ? `<div class="actions"><a href="/admin/products/${p.id}/edit?category_id=${state.selectedCategoryId || ''}" class="btn btn--ghost btn--sm">Изм.</a><button class="btn btn--danger btn--sm" onclick="deleteProduct(${Number(p.id)}, ${jsLiteral(p.title)})">Удалить</button></div>`
          : '-'
      }
    ];
  }

  async function loadCategoryProductAttributes() {
    if (!state.selectedCategoryId) return [];
    const data = await api.get(`/catalog/admin/categories/${state.selectedCategoryId}/attributes`);
    if (data._failed) return [];
    state.categoryProductAttributes = data.own || [];
    return state.categoryProductAttributes;
  }

  function ensureProductsTable(attributes) {
    if (!perms.canViewProducts) return null;
    const columns = buildCategoryProductColumns(attributes || []);
    const categoryChanged = Number(state.categoryProductsTableCategoryId) !== Number(state.selectedCategoryId);
    if (state.categoryProductsTable) {
      state.categoryProductsTable.container = document.getElementById('categoryProducts');
      state.categoryProductsTable.schemaEndpoint = `/catalog/admin/search/schema?category_id=${state.selectedCategoryId}`;
      state.categoryProductsTable.schema = null;
      state.categoryProductsTable.setColumns(columns, { preserveVisibility: !categoryChanged });
      if (categoryChanged) {
        state.categoryProductsTable.resetInteractionState('created_at', 'desc');
      }
      state.categoryProductsTableCategoryId = state.selectedCategoryId;
      return state.categoryProductsTable;
    }
    state.categoryProductsTable = new SmartTable({
      instanceName: 'categoryProductsTable',
      endpoint: '/catalog/admin/search',
      schemaEndpoint: '/catalog/admin/search/schema',
      containerId: 'categoryProducts',
      defaultSortBy: 'created_at',
      defaultSortDir: 'desc',
      wide: true,
      columns
    });
    state.categoryProductsTable.schemaEndpoint = `/catalog/admin/search/schema?category_id=${state.selectedCategoryId}`;
    state.categoryProductsTableCategoryId = state.selectedCategoryId;
    window.categoryProductsTable = state.categoryProductsTable;
    return state.categoryProductsTable;
  }

  window.setProductsMode = function(includeDescendants) {
    state.productsIncludeDescendants = includeDescendants;
    document.getElementById('catProductsDirect')?.classList.toggle('taxonomy-toggle__btn--active', !includeDescendants);
    document.getElementById('catProductsDesc')?.classList.toggle('taxonomy-toggle__btn--active', includeDescendants);
    window.loadCategoryProducts();
  };

  window.loadCategoryProducts = async function() {
    if (!state.selectedCategoryId || !perms.canViewProducts) return;
    const attributes = await loadCategoryProductAttributes();
    const table = ensureProductsTable(attributes);
    if (!table) return;
    const staticFilters = [
      {
        key: 'category_id',
        op: 'eq',
        val: String(state.selectedCategoryId),
        label: 'Категория',
        displayVal: categoryPath(state.selectedCategory)
      }
    ];
    if (state.productsIncludeDescendants) {
      staticFilters.push({
        key: 'include_descendants',
        op: 'eq',
        val: 'true',
        label: 'Подкатегории',
        displayVal: 'включены'
      });
    }
    table.setStaticFilters(staticFilters);
  };

  window.deleteProduct = async function(id, title) {
    if (!perms.canEditProducts) return;
    const confirmed = await confirmDanger('Удалить товар?', `«${title}» и все фотографии будут удалены безвозвратно.`);
    if (!confirmed) return;
    const res = await api.del('/catalog/' + id);
    if (res._failed) return;
    showToast('Товар удален', 'success');
    if (state.categoryProductsTable) state.categoryProductsTable.load();
    window.reloadCatalogTree(state.selectedCategoryId);
  };

  window.createDemoData = async function() {
    if (!perms.canCreateDemoData) return;
    if (!window.confirm('Создать недостающие демо-данные для конечных категорий?')) return;
    const res = await api.post('/catalog/admin/demo-data', {});
    if (res._failed) return;
    showToast(`Создано товаров: ${res.products_created || 0}, категорий: ${res.categories_created || 0}`, 'success');
    window.reloadCatalogTree(state.selectedCategoryId);
  };

  window.openCatalogTags = function() {
    detailPanel().innerHTML = `
      <div class="catalog-category-head">
        <div>
          <div class="catalog-category-head__path">Глобальный справочник</div>
          <h3 class="catalog-category-head__title">Теги</h3>
          <div class="catalog-category-head__meta">Теги применяются к товарам независимо от категории.</div>
        </div>
        ${perms.canEditTaxonomy ? '<button class="btn btn--primary btn--sm" type="button" onclick="openTagForm()">+ Новый тег</button>' : ''}
      </div>
      <div id="catalogTagsContainer"></div>
    `;
    ensureTagsTable().load();
  };

  function ensureTagsTable() {
    if (state.tagsTable) {
      state.tagsTable.container = document.getElementById('catalogTagsContainer');
      return state.tagsTable;
    }
    state.tagsTable = new SmartTable({
      instanceName: 'tagsTable',
      endpoint: '/catalog/admin/tags',
      schemaEndpoint: '/catalog/admin/tags/search/schema',
      containerId: 'catalogTagsContainer',
      defaultSortBy: 'sort_order',
      defaultSortDir: 'asc',
      wide: true,
      columns: [
        { key: 'id', label: '#', sortable: true },
        { key: 'title', label: 'Название', sortable: true },
        { key: 'slug', label: 'Slug', sortable: true },
        { key: 'color', label: 'Цвет', sortable: false, render: t => `<span class="tag-color"><span style="background:${esc(t.color)}"></span>${esc(t.color)}</span>` },
        { key: 'product_count', label: 'Товаров', sortable: false },
        { key: 'is_active', label: 'Активен', sortable: true, render: t => t.is_active ? 'Да' : 'Нет' },
        { key: 'actions', label: 'Действия', sortable: false, render: t => perms.canEditTaxonomy ? `<div class="actions"><button class="btn btn--ghost btn--sm" onclick="openTagForm(${jsLiteral(t)})">Изм.</button><button class="btn btn--danger btn--sm" onclick="deleteTag(${Number(t.id)})">Удалить</button></div>` : '-' }
      ]
    });
    window.tagsTable = state.tagsTable;
    return state.tagsTable;
  }

  window.openTagForm = function(tag) {
    state.editingTagId = tag ? tag.id : null;
    document.getElementById('tagModalTitle').textContent = tag ? 'Редактировать тег' : 'Новый тег';
    document.getElementById('tag-title').value = tag ? tag.title : '';
    document.getElementById('tag-slug').value = tag ? tag.slug : '';
    document.getElementById('tag-color').value = tag ? tag.color : '#7c8c6e';
    document.getElementById('tag-active').checked = tag ? tag.is_active : true;
    document.getElementById('tagModal').classList.add('modal-overlay--active');
  };

  window.closeTagForm = function() {
    document.getElementById('tagModal').classList.remove('modal-overlay--active');
  };

  window.saveTag = async function(event) {
    event.preventDefault();
    if (!perms.canEditTaxonomy) return;
    const payload = {
      title: document.getElementById('tag-title').value,
      slug: document.getElementById('tag-slug').value || null,
      color: document.getElementById('tag-color').value,
      is_active: document.getElementById('tag-active').checked
    };
    const res = state.editingTagId
      ? await api.put('/catalog/admin/tags/' + state.editingTagId, payload)
      : await api.post('/catalog/admin/tags', payload);
    if (res._failed) return;
    window.closeTagForm();
    showToast('Тег сохранен', 'success');
    ensureTagsTable().load();
  };

  window.deleteTag = async function(id) {
    if (!perms.canEditTaxonomy) return;
    if (!window.confirm('Удалить тег?')) return;
    const res = await api.del('/catalog/admin/tags/' + id);
    if (res._failed) return;
    showToast('Тег удален', 'success');
    ensureTagsTable().load();
  };

  window.categoryTree = new TaxonomyTree({
    containerId: 'categoryTree',
    onSelect: renderCategoryWorkspace,
    showActions: false,
    selectFirst: shouldAutoSelectCategory(),
  });

  window.categoryTree.load(initialCategoryIdFromLocation()).then(() => {
    if (initialView() === 'tags') {
      window.openCatalogTags();
    }
  });
})();
