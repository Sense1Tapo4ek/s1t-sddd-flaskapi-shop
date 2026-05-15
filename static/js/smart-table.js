const OP_LABELS = {
  eq: '=',
  ilike: 'содержит',
  gte: '≥',
  lte: '≤'
};

const HTMX_HINT_FLAG = 'bulkHtmxResetHintShown';

function jsLiteral(value) {
  return esc(JSON.stringify(value == null ? '' : value));
}

function dispatchToast(message, type) {
  document.body.dispatchEvent(new CustomEvent('showToast', {
    detail: { message: message, type: type || 'info' }
  }));
}

function bulkText(key, params) {
  return (typeof window.bulkT === 'function') ? window.bulkT(key, params) : key;
}

class SmartTable {
  constructor({
    instanceName,
    endpoint,
    schemaEndpoint,
    containerId,
    columns,
    defaultSortBy = 'id',
    defaultSortDir = 'desc',
    emptyText = 'Нет данных',
    staticFilters = [],
    wide = false,
    selectable = false,
    rowIdKey = 'id',
    onSelectionChange = null,
    getRowName = null
  }) {
    this.instanceName = instanceName;
    this.endpoint = endpoint;
    this.schemaEndpoint = schemaEndpoint;
    this.container = document.getElementById(containerId);
    this.emptyText = emptyText;
    this.staticFilters = staticFilters || [];
    this.wide = Boolean(wide);

    this.selectable = Boolean(selectable);
    this.rowIdKey = rowIdKey;
    this.onSelectionChange = typeof onSelectionChange === 'function' ? onSelectionChange : null;
    this.getRowName = typeof getRowName === 'function' ? getRowName : null;

    this.columns = columns.map(c => ({ ...c, visible: c.visible !== false }));
    this.schema = null;
    this.searchQuery = '';

    this.state = {
      page: 1, limit: 20, sort_by: defaultSortBy, sort_dir: defaultSortDir,
      activeFilters: []
    };
    this.lastData = null;
    this.openPopoverKey = null;
    this.configOpen = false;

    this.selection = {
      mode: 'empty',          // 'empty' | 'ids' | 'all_by_filter'
      ids: new Set(),         // string ids when mode === 'ids'
      lastClickedIdx: null,   // for Shift+click range
      masterMenuOpen: false
    };

    this._handleOutsideClick = (e) => {
      const popoverOpen = !!this.openPopoverKey || this.configOpen;
      const menuOpen = this.selection.masterMenuOpen;
      if (!popoverOpen && !menuOpen) return;
      if (e.target.closest('.filter-popover')) return;
      if (e.target.closest('.bulk-master')) return;
      this.openPopoverKey = null;
      this.configOpen = false;
      this.selection.masterMenuOpen = false;
      this.render();
    };

    this._handleKeyDown = (e) => {
      if (e.key !== 'Escape') return;
      if (!this.selectable) return;
      if (this.selection.mode === 'empty') return;
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      this.clearSelection();
    };

    document.addEventListener('click', this._handleOutsideClick);
    document.addEventListener('keydown', this._handleKeyDown);
  }

  destroy() {
    document.removeEventListener('click', this._handleOutsideClick);
    document.removeEventListener('keydown', this._handleKeyDown);
    if (this.selectable) {
      this._clearSelectionInternal('htmx-rebuild');
      this._notifySelectionChange();
    }
  }

  // ─── Selection API ──────────────────────────────────────────────────

  getSelection() {
    const mode = this.selection.mode;
    if (mode === 'empty') return { mode, total: 0 };
    if (mode === 'ids') {
      return {
        mode,
        ids: Array.from(this.selection.ids),
        total: this.selection.ids.size
      };
    }
    return {
      mode,
      filter: this._currentFilterSnapshot(),
      total: this.lastData ? this.lastData.total : 0
    };
  }

  clearSelection() {
    if (this.selection.mode === 'empty') return;
    this._clearSelectionInternal('user');
    this._notifySelectionChange();
    this.render();
  }

  selectPage() {
    if (!this.lastData || !this.lastData.items) return;
    const pageIds = this._currentPageIds();
    this.selection.mode = 'ids';
    this.selection.ids = new Set(pageIds);
    this.selection.masterMenuOpen = false;
    this._notifySelectionChange();
    this.render();
  }

  selectAllByFilter() {
    this.selection.mode = 'all_by_filter';
    this.selection.ids.clear();
    this.selection.masterMenuOpen = false;
    this._notifySelectionChange();
    this.render();
  }

  toggleRow(id, idx, shiftKey) {
    if (this.selection.mode === 'all_by_filter') {
      // Switching from filter-mode back to explicit selection.
      const pageIds = this._currentPageIds();
      this.selection.ids = new Set(pageIds);
      this.selection.mode = 'ids';
    }
    if (shiftKey && this.selection.lastClickedIdx != null && this.lastData && this.lastData.items) {
      const a = Math.min(this.selection.lastClickedIdx, idx);
      const b = Math.max(this.selection.lastClickedIdx, idx);
      const want = !this.selection.ids.has(String(id));
      for (let i = a; i <= b; i++) {
        const item = this.lastData.items[i];
        if (!item) continue;
        const rid = String(item[this.rowIdKey]);
        if (want) this.selection.ids.add(rid);
        else this.selection.ids.delete(rid);
      }
    } else {
      const sid = String(id);
      if (this.selection.ids.has(sid)) this.selection.ids.delete(sid);
      else this.selection.ids.add(sid);
    }
    this.selection.lastClickedIdx = idx;
    this.selection.mode = this.selection.ids.size === 0 ? 'empty' : 'ids';
    this._notifySelectionChange();
    this.render();
  }

  toggleMasterMenu() {
    if (!this.selectable) return;
    this.selection.masterMenuOpen = !this.selection.masterMenuOpen;
    this.render();
  }

  markFailedRows(ids) {
    if (!ids || !ids.length) return;
    const idSet = new Set(ids.map(String));
    const rows = this.container.querySelectorAll('tr[data-row-id]');
    rows.forEach(tr => {
      const rid = tr.getAttribute('data-row-id');
      if (idSet.has(rid)) {
        tr.classList.add('is-flashing-failed');
        setTimeout(() => tr.classList.remove('is-flashing-failed'), 1600);
      }
    });
  }

  buildFailureRows(failed) {
    // For BulkActionBar: enrich {id, reason} with name where possible.
    if (!failed) return [];
    const itemsById = new Map();
    if (this.lastData && this.lastData.items) {
      this.lastData.items.forEach(it => itemsById.set(String(it[this.rowIdKey]), it));
    }
    return failed.map(f => {
      const item = itemsById.get(String(f.id));
      let name = null;
      if (item) {
        if (this.getRowName) name = this.getRowName(item);
        else name = item.name || item.title || item.label || null;
      }
      return { id: f.id, reason: f.reason, name: name };
    });
  }

  // ─── Selection internals ────────────────────────────────────────────

  _clearSelectionInternal(reason) {
    const prev = this.selection.mode;
    this.selection.mode = 'empty';
    this.selection.ids.clear();
    this.selection.lastClickedIdx = null;
    this.selection.masterMenuOpen = false;

    if (reason === 'filter-change' && prev === 'all_by_filter') {
      dispatchToast(bulkText('bulk.filterChanged'), 'info');
    }
    if (reason === 'htmx-rebuild' && prev !== 'empty') {
      try {
        if (!sessionStorage.getItem(HTMX_HINT_FLAG)) {
          dispatchToast(bulkText('bulk.htmxReset.hint'), 'info');
          sessionStorage.setItem(HTMX_HINT_FLAG, '1');
        }
      } catch (_) { /* sessionStorage may be unavailable */ }
    }
  }

  _notifySelectionChange() {
    if (this.onSelectionChange) {
      try { this.onSelectionChange(this.getSelection()); } catch (e) { console.error(e); }
    }
  }

  _currentPageIds() {
    if (!this.lastData || !this.lastData.items) return [];
    return this.lastData.items.map(it => String(it[this.rowIdKey]));
  }

  _currentFilterSnapshot() {
    const out = {};
    if (this.searchQuery) out.q = this.searchQuery;
    [...this.staticFilters, ...this.state.activeFilters].forEach(f => {
      const key = f.op === 'eq' ? f.key : `${f.key}__${f.op}`;
      out[key] = f.val;
    });
    return out;
  }

  async load() {
    this.container.innerHTML = '<p class="loading-text">Загрузка…</p>';

    if (!this.schema && this.schemaEndpoint) {
      const res = await api.get(this.schemaEndpoint);
      this.schema = res.fields || [];
    }

    const params = new URLSearchParams({ page: this.state.page, limit: this.state.limit });
    if (this.state.sort_by) params.set('sort_by', this.state.sort_by);
    if (this.state.sort_dir) params.set('sort_dir', this.state.sort_dir);
    if (this.searchQuery) params.set('q', this.searchQuery);

    [...this.staticFilters, ...this.state.activeFilters].forEach(f => {
      const paramKey = f.op === 'eq' ? f.key : `${f.key}__${f.op}`;
      params.append(paramKey, f.val);
    });

    this.lastData = await api.get(`${this.endpoint}?${params.toString()}`);
    this.render();
  }

  handleSort(key) {
    if (this.state.sort_by === key) {
      this.state.sort_dir = this.state.sort_dir === 'asc' ? 'desc' : 'asc';
    } else {
      this.state.sort_by = key;
      this.state.sort_dir = 'asc';
    }
    this.state.page = 1;
    if (this.selectable && this.selection.mode !== 'empty') {
      this._clearSelectionInternal('filter-change');
      this._notifySelectionChange();
    }
    this.load();
  }

  togglePopover(key) {
    this.openPopoverKey = this.openPopoverKey === key ? null : key;
    this.render();
  }

  applyFilter(key, op, val, columnLabel) {
    if (val === '') return;
    const existingIdx = this.state.activeFilters.findIndex(f => f.key === key && f.op === op);
    const filterObj = { key, op, val, label: columnLabel };
    if (existingIdx > -1) {
      this.state.activeFilters[existingIdx] = filterObj;
    } else {
      this.state.activeFilters.push(filterObj);
    }
    this.openPopoverKey = null;
    this.state.page = 1;
    if (this.selectable && this.selection.mode !== 'empty') {
      this._clearSelectionInternal('filter-change');
      this._notifySelectionChange();
    }
    this.load();
  }

  removeFilter(index) {
    this.state.activeFilters.splice(index, 1);
    this.state.page = 1;
    if (this.selectable && this.selection.mode !== 'empty') {
      this._clearSelectionInternal('filter-change');
      this._notifySelectionChange();
    }
    this.load();
  }

  setPage(page) {
    const totalPages = this.lastData ? Math.max(1, Math.ceil(this.lastData.total / this.state.limit)) : 1;
    let p = parseInt(page, 10);
    if (isNaN(p) || p < 1) p = 1;
    if (p > totalPages) p = totalPages;
    if (this.state.page !== p) {
      this.state.page = p;
      // page change keeps all_by_filter; resets explicit ids (silently).
      if (this.selectable && this.selection.mode === 'ids') {
        this._clearSelectionInternal('page-change');
        this._notifySelectionChange();
      }
      this.load();
    }
  }

  setLimit(limit) {
    this.state.limit = parseInt(limit, 10);
    this.state.page = 1;
    if (this.selectable && this.selection.mode !== 'empty') {
      this._clearSelectionInternal('filter-change');
      this._notifySelectionChange();
    }
    this.load();
  }

  setSearchQuery(q) {
    this.searchQuery = String(q || '');
    this.state.page = 1;
    if (this.selectable && this.selection.mode !== 'empty') {
      this._clearSelectionInternal('filter-change');
      this._notifySelectionChange();
    }
    this.load();
  }

  setStaticFilters(filters) {
    this.staticFilters = filters || [];
    this.state.page = 1;
    if (this.selectable && this.selection.mode !== 'empty') {
      this._clearSelectionInternal('htmx-rebuild');
      this._notifySelectionChange();
    }
    return this.load();
  }

  setColumns(columns, { preserveVisibility = true } = {}) {
    const previousVisibility = new Map(this.columns.map(c => [c.key, c.visible]));
    this.columns = columns.map(c => ({
      ...c,
      visible: preserveVisibility && previousVisibility.has(c.key)
        ? previousVisibility.get(c.key)
        : c.visible !== false
    }));
  }

  resetInteractionState(defaultSortBy = 'id', defaultSortDir = 'desc') {
    this.state.page = 1;
    this.state.sort_by = defaultSortBy;
    this.state.sort_dir = defaultSortDir;
    this.state.activeFilters = [];
    this.searchQuery = '';
    this.openPopoverKey = null;
    this.configOpen = false;
    if (this.selectable) {
      this._clearSelectionInternal('htmx-rebuild');
      this._notifySelectionChange();
    }
  }

  toggleConfig() {
    this.configOpen = !this.configOpen;
    this.render();
  }

  toggleColumn(key) {
    const col = this.columns.find(c => c.key === key);
    if (!col) return;
    const visibleCount = this.columns.filter(c => c.visible).length;
    if (col.visible && visibleCount === 1) {
      document.body.dispatchEvent(new CustomEvent('showToast', {
        detail: { message: 'Минимум одна колонка должна оставаться видимой', type: 'error' }
      }));
      this.render();
      return;
    }
    col.visible = !col.visible;
    this.render();
  }

  // ─── Rendering helpers ──────────────────────────────────────────────

  _renderMasterCell(tableRef) {
    const data = this.lastData;
    const pageIds = this._currentPageIds();
    const sel = this.selection;
    const pageCount = pageIds.length;
    const total = data ? data.total : 0;

    let aria = 'false';
    let glyph = '';
    if (sel.mode === 'all_by_filter') { aria = 'true'; glyph = '☑'; }
    else if (sel.mode === 'ids') {
      const allOnPage = pageIds.every(id => sel.ids.has(id));
      const noneOnPage = pageIds.every(id => !sel.ids.has(id));
      if (allOnPage && pageCount > 0) { aria = 'true'; glyph = '☑'; }
      else if (!noneOnPage) { aria = 'mixed'; glyph = '▣'; }
      else { aria = 'false'; glyph = ''; }
    }

    const showAllOption = total > pageCount;
    const showClearOption = sel.mode !== 'empty';

    const menu = sel.masterMenuOpen ? `
      <div class="bulk-master__menu" onclick="event.stopPropagation()">
        <button class="bulk-master__item" type="button"
          onclick="${tableRef}.selectPage()">
          <span>${esc(bulkText('bulk.master.page', { n: pageCount }))}</span>
        </button>
        ${showAllOption ? `
          <button class="bulk-master__item" type="button"
            onclick="${tableRef}.selectAllByFilter()">
            <span>${esc(bulkText('bulk.master.all', { total: total }))}</span>
          </button>` : ''}
        ${showClearOption ? `
          <div class="bulk-master__sep"></div>
          <button class="bulk-master__item" type="button"
            onclick="${tableRef}.clearSelection()">
            <span>${esc(bulkText('bulk.master.unselect'))}</span>
          </button>` : ''}
      </div>
    ` : '';

    return `
      <th class="smart-table__sel" style="position:relative;">
        <div class="bulk-master">
          <button type="button"
            class="bulk-master__trigger"
            aria-haspopup="menu"
            aria-expanded="${sel.masterMenuOpen}"
            aria-checked="${aria}"
            aria-label="Управление выделением"
            onclick="event.stopPropagation(); ${tableRef}.toggleMasterMenu()">${esc(glyph)}</button>
          ${menu}
        </div>
      </th>
    `;
  }

  _renderRowSelCell(item, idx, tableRef) {
    const sid = String(item[this.rowIdKey]);
    const checked = this.selection.mode === 'all_by_filter' || this.selection.ids.has(sid);
    return `
      <td class="smart-table__sel">
        <label class="smart-checkbox">
          <input type="checkbox" ${checked ? 'checked' : ''}
            onclick="event.stopPropagation(); ${tableRef}.toggleRow(${jsLiteral(sid)}, ${idx}, event.shiftKey)">
          <span class="smart-checkbox__box"></span>
        </label>
      </td>
    `;
  }

  render() {
    const data = this.lastData;
    const visibleCols = this.columns.filter(c => c.visible);
    const tableRef = `window[${jsLiteral(this.instanceName)}]`;

    const staticFiltersHTML = this.staticFilters.map(f => `
      <div class="filter-chip filter-chip--static">
        <span>${esc(f.label)} ${OP_LABELS[f.op] || f.op}</span>
        <span class="filter-chip__val">${esc(f.displayVal || f.val)}</span>
      </div>
    `).join('');

    const activeFiltersHTML = this.state.activeFilters.map((f, idx) => `
      <div class="filter-chip">
        <span>${esc(f.label)} ${OP_LABELS[f.op] || f.op}</span>
        <span class="filter-chip__val">${esc(f.val)}</span>
        <button class="filter-chip__del" onclick="${tableRef}.removeFilter(${idx})">&times;</button>
      </div>
    `).join('');

    if (!data || !data.items) {
      this.container.innerHTML = '<p class="empty-text">Ошибка загрузки или нет данных</p>';
      return;
    }

    const dataHeaders = visibleCols.map(c => {
      let thContent = c.sortable
        ? `<button type="button" class="sortable th-sort-btn" onclick="${tableRef}.handleSort(${jsLiteral(c.key)})" aria-label="Сортировать по ${esc(c.label)}">${esc(c.label)}</button>`
        : `<span class="th-label">${esc(c.label)}</span>`;

      if (c.sortable) {
        let icon = '↕', iconClass = 'sort-icon';
        if (this.state.sort_by === c.key) {
          icon = this.state.sort_dir === 'asc' ? '↑' : '↓';
          iconClass += ' sort-icon--active';
        }
        thContent += `<span class="${iconClass}">${icon}</span>`;
      }

      const schemaField = this.schema ? this.schema.find(f => f.key === c.key) : null;
      let filterBtnHTML = '';
      let popoverHTML = '';

      if (schemaField) {
        filterBtnHTML = `<button class="th-filter-btn" onclick="event.stopPropagation(); ${tableRef}.togglePopover(${jsLiteral(c.key)})">+</button>`;

        if (this.openPopoverKey === c.key) {
          const singleOp = schemaField.operators.length === 1;
          const operatorId = `popop_${c.key}`;
          const valueId = `popval_${c.key}`;
          const applyCall = `${tableRef}.applyFilter(${jsLiteral(c.key)}, document.getElementById(${jsLiteral(operatorId)}).value, document.getElementById(${jsLiteral(valueId)}).value, ${jsLiteral(c.label)})`;

          let operatorHTML = '';
          if (singleOp) {
            const op = schemaField.operators[0];
            operatorHTML = `
              <div class="filter-op-label">${OP_LABELS[op] || op}</div>
              <input type="hidden" id="${esc(operatorId)}" value="${esc(op)}">
            `;
          } else {
            const operatorOptions = schemaField.operators.map(op =>
              `<option value="${op}">${OP_LABELS[op] || op}</option>`
            ).join('');
            operatorHTML = `
              <div class="select-wrapper">
                <select id="${esc(operatorId)}" class="form-input form-input--sm">${operatorOptions}</select>
              </div>
            `;
          }

          let inputHTML = '';
          if (schemaField.type === 'enum' && schemaField.options) {
            const opts = schemaField.options.map(o => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('');
            inputHTML = `
              <div class="select-wrapper">
                <select id="${esc(valueId)}" class="form-input form-input--sm">${opts}</select>
              </div>
            `;
          } else {
            let inputType = 'text';
            if (schemaField.type === 'number') inputType = 'number';
            if (schemaField.type === 'date') inputType = 'date';
            inputHTML = `<input id="${esc(valueId)}" type="${inputType}" class="form-input form-input--sm" placeholder="Значение…"
              onkeydown="if(event.key==='Enter'){event.preventDefault();${applyCall};}">`;
          }

          popoverHTML = `
            <div class="filter-popover" onclick="event.stopPropagation()">
              <div class="filter-popover__title">Фильтр: ${esc(c.label)}</div>
              <div class="filter-popover__body">
                ${operatorHTML}
                ${inputHTML}
              </div>
              <button class="btn btn--primary btn--sm btn--full" style="margin-top:10px;" onclick="${applyCall}">Применить</button>
            </div>
          `;
        }
      }

      return `<th style="position:relative;">${thContent}${filterBtnHTML}${popoverHTML}</th>`;
    }).join('');

    const selHeader = this.selectable ? this._renderMasterCell(tableRef) : '';
    const headers = selHeader + dataHeaders;

    const totalCols = visibleCols.length + (this.selectable ? 1 : 0);

    const rowsHTML = data.items.map((item, idx) => {
      const sid = String(item[this.rowIdKey]);
      const selCell = this.selectable ? this._renderRowSelCell(item, idx, tableRef) : '';
      const isSel = this.selectable && (this.selection.mode === 'all_by_filter' || this.selection.ids.has(sid));
      const cells = visibleCols.map(c => `<td>${c.render ? c.render(item, idx, data.items) : esc(item[c.key])}</td>`).join('');
      return `<tr data-row-id="${esc(sid)}"${isSel ? ' class="is-selected"' : ''}>${selCell}${cells}</tr>`;
    }).join('') || `<tr><td colspan="${totalCols}" style="text-align:center; color:var(--color-text-muted); padding:24px;">${this.emptyText}</td></tr>`;

    const pages = Math.max(1, Math.ceil(data.total / this.state.limit));
    const isFirst = this.state.page <= 1;
    const isLast = this.state.page >= pages;

    const columnsConfigHTML = `
      <div style="position:relative;">
        <button class="btn btn--ghost btn--sm" onclick="event.stopPropagation(); ${tableRef}.toggleConfig()">Колонки</button>
        ${this.configOpen ? `
          <div class="filter-popover" style="position:absolute; right:0; left:auto; top:calc(100% + 8px); padding:16px; min-width:200px; z-index:9999; max-height:350px; overflow-y:auto;">
            <div class="filter-popover__title" style="margin-bottom:12px;">Видимые колонки</div>
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${this.columns.map(c => `
                <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:13px;">
                  <input type="checkbox" ${c.visible ? 'checked' : ''} onchange="${tableRef}.toggleColumn(${jsLiteral(c.key)})">
                  ${esc(c.label)}
                </label>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    `;

    const searchHTML = `
      <input type="search" class="form-input form-input--sm"
             style="width:240px;"
             placeholder="Поиск по названию и описанию…"
             value="${esc(this.searchQuery || '')}"
             oninput="${tableRef}.setSearchQuery(this.value)">
    `;

    const topControlsHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; flex-wrap:wrap;">
        <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
          ${searchHTML}
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:13px; color:var(--color-text-muted);">Показывать:</span>
            <select class="form-input form-input--sm" style="width:auto;" onchange="${tableRef}.setLimit(this.value)">
              <option value="10" ${this.state.limit === 10 ? 'selected' : ''}>10</option>
              <option value="20" ${this.state.limit === 20 ? 'selected' : ''}>20</option>
              <option value="50" ${this.state.limit === 50 ? 'selected' : ''}>50</option>
            </select>
          </div>
          ${columnsConfigHTML}
        </div>
        <div style="display:flex; align-items:center; gap:4px;">
          <button class="btn btn--ghost btn--sm" ${isFirst ? 'disabled' : ''} onclick="${tableRef}.setPage(1)">&laquo;</button>
          <button class="btn btn--ghost btn--sm" ${isFirst ? 'disabled' : ''} onclick="${tableRef}.setPage(${this.state.page - 1})">&lsaquo;</button>
          <span style="font-size:13px; color:var(--color-text-muted); display:flex; align-items:center; gap:6px; margin:0 4px;">
            стр.
            <input type="number" class="form-input form-input--sm" style="width:50px; text-align:center;" value="${this.state.page}" min="1" max="${pages}" onchange="${tableRef}.setPage(this.value)">
            из ${pages} &nbsp;·&nbsp; всего: ${data.total}
          </span>
          <button class="btn btn--ghost btn--sm" ${isLast ? 'disabled' : ''} onclick="${tableRef}.setPage(${this.state.page + 1})">&rsaquo;</button>
          <button class="btn btn--ghost btn--sm" ${isLast ? 'disabled' : ''} onclick="${tableRef}.setPage(${pages})">&raquo;</button>
        </div>
      </div>
    `;

    this.container.innerHTML = `
      ${staticFiltersHTML || activeFiltersHTML ? `<div class="active-filters">${staticFiltersHTML}${activeFiltersHTML}</div>` : ''}
      ${topControlsHTML}
      <div class="${this.wide ? 'smart-table smart-table--wide' : ''}" style="border:1px solid var(--color-border); border-radius:var(--radius); ${this.wide ? 'overflow-x:auto;' : 'overflow:hidden;'}">
        <table class="table">
          <thead><tr>${headers}</tr></thead>
          <tbody>${rowsHTML}</tbody>
        </table>
      </div>
    `;
  }
}
