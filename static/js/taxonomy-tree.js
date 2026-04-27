(function() {
  'use strict';

  const DEFAULT_TREE_ENDPOINT = '/catalog/admin/categories/tree';

  function escapeHtml(value) {
    if (typeof esc === 'function') return esc(value);
    if (value == null) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getApiClient() {
    try {
      if (typeof api !== 'undefined') return api;
    } catch (_) {}
    return null;
  }

  async function getJson(url) {
    const client = getApiClient();
    if (client) return client.get(url);
    const response = await fetch(url, { credentials: 'same-origin' });
    return response.json().catch(() => ({}));
  }

	  async function sendJson(method, url, body) {
	    const client = getApiClient();
	    if (client) {
      if (method === 'POST') return client.post(url, body);
      if (method === 'PUT') return client.put(url, body);
      if (method === 'PATCH') return client.patch(url, body);
      if (method === 'DELETE') return client.del(url, body);
    }
	    const response = await fetch(url, {
	      method,
	      credentials: 'same-origin',
	      headers: {
	        'Content-Type': 'application/json',
	        ...(typeof getCsrfToken === 'function' ? { 'X-CSRF-Token': getCsrfToken() } : {}),
	      },
	      body: body == null ? undefined : JSON.stringify(body),
	    });
    return response.json().catch(() => ({}));
  }

  function normalizeTree(data) {
    if (Array.isArray(data)) return data;
    if (!data || typeof data !== 'object') return [];
    const source = data.items || data.categories || data.tree || data.data || [];
    return Array.isArray(source) ? source : [];
  }

  function childNodes(category) {
    return Array.isArray(category && category.children) ? category.children : [];
  }

  function categoryCount(category) {
    return category.product_count ?? category.products_count ?? category.products ?? category.count ?? 0;
  }

  function findCategory(nodes, id) {
    const target = Number(id);
    for (const node of nodes || []) {
      if (Number(node.id) === target) return node;
      const found = findCategory(childNodes(node), target);
      if (found) return found;
    }
    return null;
  }

  function flattenTree(nodes, depth = 0, parentPath = []) {
    const result = [];
    for (const node of nodes || []) {
      const path = parentPath.concat(node.title || node.slug || node.id);
      result.push({ ...node, depth, path });
      result.push(...flattenTree(childNodes(node), depth + 1, path));
    }
    return result;
  }

  function annotateTree(nodes, parentPath = []) {
    return (nodes || []).map(node => {
      const path = parentPath.concat(node.title || node.slug || node.id);
      return {
        ...node,
        path,
        children: annotateTree(childNodes(node), path),
      };
    });
  }

  function descendantIds(category) {
    const ids = [];
    for (const child of childNodes(category)) {
      ids.push(Number(child.id));
      ids.push(...descendantIds(child));
    }
    return ids;
  }

  function showToast(message, type) {
    document.body.dispatchEvent(new CustomEvent('showToast', {
      detail: { message, type: type || 'info' }
    }));
  }

  class TaxonomyTree {
    constructor(options) {
      this.container = typeof options.containerId === 'string'
        ? document.getElementById(options.containerId)
        : options.container;
      this.endpoint = options.endpoint || DEFAULT_TREE_ENDPOINT;
      this.selectedId = options.selectedId ? Number(options.selectedId) : null;
      this.onSelect = options.onSelect || function() {};
      this.onAddChild = options.onAddChild || null;
      this.onMove = options.onMove || null;
      this.showActions = options.showActions !== false;
      this.selectFirst = options.selectFirst !== false;
      this.emptyText = options.emptyText || 'Категории не созданы';
      this.tree = [];
      this.collapsedIds = new Set(options.collapsedIds || []);

      if (!this.container) return;
      this.container.addEventListener('click', (event) => this.handleClick(event));
    }

    async load(preferredId) {
      if (!this.container) return;
      this.container.innerHTML = '<p class="loading-text">Загрузка…</p>';
      const response = await getJson(this.endpoint);
      if (response && response._failed) {
        this.container.innerHTML = '<p class="empty-text">Не удалось загрузить категории</p>';
        return;
      }
      this.tree = annotateTree(normalizeTree(response));
      if (preferredId) this.selectedId = Number(preferredId);
      if (this.selectFirst && !this.selectedId && this.tree.length) {
        this.selectedId = Number(this.tree[0].id);
      }
      this.render();
      const selected = this.getSelected();
      if (selected) this.onSelect(selected);
    }

    handleClick(event) {
      const toggleEl = event.target.closest('[data-taxonomy-toggle]');
      if (toggleEl && this.container.contains(toggleEl)) {
        event.preventDefault();
        event.stopPropagation();
        const id = Number(toggleEl.dataset.categoryId);
        if (this.collapsedIds.has(id)) {
          this.collapsedIds.delete(id);
        } else {
          this.collapsedIds.add(id);
        }
        this.render();
        return;
      }

      const actionEl = event.target.closest('[data-taxonomy-action]');
      if (actionEl && this.container.contains(actionEl)) {
        event.preventDefault();
        event.stopPropagation();
        const id = Number(actionEl.dataset.categoryId);
        const category = findCategory(this.tree, id);
        const action = actionEl.dataset.taxonomyAction;
        if (!category) return;
        if (action === 'add' && this.onAddChild) this.onAddChild(category);
        if ((action === 'up' || action === 'down') && this.onMove) this.onMove(category, action);
        return;
      }

      const row = event.target.closest('[data-taxonomy-id]');
      if (!row || !this.container.contains(row)) return;
      this.select(Number(row.dataset.taxonomyId));
    }

    getSelected() {
      return this.selectedId ? findCategory(this.tree, this.selectedId) : null;
    }

    select(id, options) {
      this.selectedId = Number(id);
      this.render();
      if (!options || options.emit !== false) {
        const selected = this.getSelected();
        if (selected) this.onSelect(selected);
      }
    }

    render() {
      if (!this.container) return;
      if (!this.tree.length) {
        this.container.innerHTML = `<p class="empty-text">${escapeHtml(this.emptyText)}</p>`;
        return;
      }
      this.container.innerHTML = `<div class="taxonomy-tree">${this.tree.map(node => this.renderNode(node, 0)).join('')}</div>`;
    }

    renderNode(category, depth) {
      const children = childNodes(category);
      const isActive = Number(category.id) === Number(this.selectedId);
      const inactive = category.is_active === false;
      const count = categoryCount(category);
      const collapsed = this.collapsedIds.has(Number(category.id));
      const toggle = children.length
        ? `<button type="button" class="taxonomy-tree__toggle" data-taxonomy-toggle data-category-id="${category.id}" aria-label="${collapsed ? 'Развернуть' : 'Свернуть'} ${escapeHtml(category.title || '')}" aria-expanded="${collapsed ? 'false' : 'true'}">${collapsed ? '▸' : '▾'}</button>`
        : '<span class="taxonomy-tree__toggle" aria-hidden="true"></span>';
      const actions = this.showActions ? `
        <span class="taxonomy-tree__actions">
          <button type="button" class="taxonomy-tree__action" data-taxonomy-action="add" data-category-id="${category.id}" title="Добавить дочернюю">+</button>
          <button type="button" class="taxonomy-tree__action" data-taxonomy-action="up" data-category-id="${category.id}" title="Выше">↑</button>
          <button type="button" class="taxonomy-tree__action" data-taxonomy-action="down" data-category-id="${category.id}" title="Ниже">↓</button>
        </span>
      ` : '';

      return `
        <div class="taxonomy-tree__item">
          <div class="taxonomy-tree__row ${isActive ? 'taxonomy-tree__row--active' : ''} ${inactive ? 'taxonomy-tree__row--inactive' : ''}"
               data-taxonomy-id="${category.id}">
            <span class="taxonomy-tree__spacer" style="width:${depth * 16}px"></span>
            ${toggle}
            <span class="taxonomy-tree__label">
              <span class="taxonomy-tree__title">${escapeHtml(category.title || 'Без названия')}</span>
              <span class="taxonomy-tree__slug">${escapeHtml(category.slug || '')}</span>
            </span>
            <span class="taxonomy-tree__count">${count}</span>
            ${actions}
          </div>
          ${children.length && !collapsed ? `<div class="taxonomy-tree__children">${children.map(child => this.renderNode(child, depth + 1)).join('')}</div>` : ''}
        </div>
      `;
    }
  }

  class CategoryTreeSelect {
    constructor(options) {
      this.root = typeof options.containerId === 'string'
        ? document.getElementById(options.containerId)
        : options.container;
      this.endpoint = options.endpoint || DEFAULT_TREE_ENDPOINT;
      this.name = options.name || 'category_id';
      this.placeholder = options.placeholder || 'Выберите категорию';
      this.selectedId = options.selectedId ? Number(options.selectedId) : null;
      this.onChange = options.onChange || function() {};
      this.leafOnly = Boolean(options.leafOnly);
      this.tree = [];
      this.open = false;

      if (!this.root) return;
      this.root.addEventListener('click', (event) => this.handleClick(event));
      document.addEventListener('click', (event) => {
        if (!this.root || this.root.contains(event.target)) return;
        if (this.open) {
          this.open = false;
          this.render();
        }
      });
    }

    async load(preferredId) {
      if (!this.root) return;
      if (preferredId) this.selectedId = Number(preferredId);
      this.root.innerHTML = '<p class="loading-text">Загрузка…</p>';
      const response = await getJson(this.endpoint);
      if (response && response._failed) {
        this.root.innerHTML = '<p class="empty-text">Категории недоступны</p>';
        return;
      }
      this.tree = annotateTree(normalizeTree(response));
      this.render();
    }

    handleClick(event) {
      const button = event.target.closest('[data-tree-select-toggle]');
      if (button && this.root.contains(button)) {
        event.preventDefault();
        this.open = !this.open;
        this.render();
        return;
      }

      const row = event.target.closest('[data-tree-select-id]');
      if (!row || !this.root.contains(row)) return;
      event.preventDefault();
      const id = Number(row.dataset.treeSelectId);
      const category = findCategory(this.tree, id);
      if (!category) return;
      if (this.leafOnly && childNodes(category).length) {
        showToast('Выберите конечную категорию без подкатегорий', 'error');
        return;
      }
      this.select(id);
    }

    select(id, options) {
      this.selectedId = id ? Number(id) : null;
      this.open = false;
      this.render();
      if (!options || options.emit !== false) {
        this.onChange(this.getSelected());
      }
    }

    getSelected() {
      return this.selectedId ? findCategory(this.tree, this.selectedId) : null;
    }

    getValue() {
      return this.selectedId;
    }

    render() {
      if (!this.root) return;
      const selected = this.getSelected();
      const label = selected ? selected.title : this.placeholder;
      this.root.innerHTML = `
        <div class="tree-select">
          <input type="hidden" name="${escapeHtml(this.name)}" value="${this.selectedId || ''}">
          <button type="button" class="btn btn--ghost tree-select__button" data-tree-select-toggle>
            <span>${escapeHtml(label)}</span>
            <span>▾</span>
          </button>
          <div class="tree-select__menu" ${this.open ? '' : 'hidden'}>
            ${this.tree.length ? this.tree.map(node => this.renderNode(node, 0)).join('') : '<p class="empty-text">Категории не созданы</p>'}
          </div>
        </div>
      `;
    }

    renderNode(category, depth) {
      const children = childNodes(category);
      const isActive = Number(category.id) === Number(this.selectedId);
      const inactive = category.is_active === false;
      return `
        <div class="taxonomy-tree__item">
          <div class="taxonomy-tree__row ${isActive ? 'taxonomy-tree__row--active' : ''} ${inactive ? 'taxonomy-tree__row--inactive' : ''}"
               data-tree-select-id="${category.id}">
            <span class="taxonomy-tree__spacer" style="width:${depth * 16}px"></span>
            <span class="taxonomy-tree__toggle">${children.length ? '▾' : ''}</span>
            <span class="taxonomy-tree__label">
              <span class="taxonomy-tree__title">${escapeHtml(category.title || 'Без названия')}</span>
              <span class="taxonomy-tree__slug">${escapeHtml(category.slug || '')}</span>
            </span>
          </div>
          ${children.length ? `<div class="taxonomy-tree__children">${children.map(child => this.renderNode(child, depth + 1)).join('')}</div>` : ''}
        </div>
      `;
    }
  }

  window.TaxonomyApi = {
    DEFAULT_TREE_ENDPOINT,
    childNodes,
    categoryCount,
    descendantIds,
    escapeHtml,
    findCategory,
    flattenTree,
    annotateTree,
    getJson,
    normalizeTree,
    sendJson,
  };
  window.TaxonomyTree = TaxonomyTree;
  window.CategoryTreeSelect = CategoryTreeSelect;
})();
