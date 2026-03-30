const OP_LABELS = {
  eq: '=',
  ilike: 'содержит',
  gte: '≥',
  lte: '≤'
};

class SmartTable {
  constructor({ instanceName, endpoint, schemaEndpoint, containerId, columns, defaultSortBy = 'id', defaultSortDir = 'desc', emptyText = 'Нет данных' }) {
    this.instanceName = instanceName;
    this.endpoint = endpoint;
    this.schemaEndpoint = schemaEndpoint;
    this.container = document.getElementById(containerId);
    this.emptyText = emptyText;

    this.columns = columns.map(c => ({ ...c, visible: c.visible !== false }));
    this.schema = null;

    this.state = {
      page: 1, limit: 20, sort_by: defaultSortBy, sort_dir: defaultSortDir,
      activeFilters: []
    };
    this.lastData = null;
    this.openPopoverKey = null;
    this.configOpen = false;

    this._handleOutsideClick = (e) => {
      if (!this.openPopoverKey && !this.configOpen) return;
      if (e.target.closest('.filter-popover')) return;
      this.openPopoverKey = null;
      this.configOpen = false;
      this.render();
    };

    document.addEventListener('click', this._handleOutsideClick);
  }

  destroy() {
    document.removeEventListener('click', this._handleOutsideClick);
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

    this.state.activeFilters.forEach(f => {
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
    this.load();
  }

  removeFilter(index) {
    this.state.activeFilters.splice(index, 1);
    this.state.page = 1;
    this.load();
  }

  setPage(page) {
    const totalPages = this.lastData ? Math.max(1, Math.ceil(this.lastData.total / this.state.limit)) : 1;
    let p = parseInt(page, 10);
    if (isNaN(p) || p < 1) p = 1;
    if (p > totalPages) p = totalPages;
    if (this.state.page !== p) {
      this.state.page = p;
      this.load();
    }
  }

  setLimit(limit) {
    this.state.limit = parseInt(limit, 10);
    this.state.page = 1;
    this.load();
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

  render() {
    const data = this.lastData;
    const visibleCols = this.columns.filter(c => c.visible);

    const activeFiltersHTML = this.state.activeFilters.map((f, idx) => `
      <div class="filter-chip">
        <span>${esc(f.label)} ${OP_LABELS[f.op] || f.op}</span>
        <span class="filter-chip__val">${esc(f.val)}</span>
        <button class="filter-chip__del" onclick="window.${this.instanceName}.removeFilter(${idx})">&times;</button>
      </div>
    `).join('');

    if (!data || !data.items) {
      this.container.innerHTML = '<p class="empty-text">Ошибка загрузки или нет данных</p>';
      return;
    }

    const headers = visibleCols.map(c => {
      let thContent = `<span class="sortable" onclick="window.${this.instanceName}.handleSort('${c.key}')">${esc(c.label)}</span>`;

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
        filterBtnHTML = `<button class="th-filter-btn" onclick="event.stopPropagation(); window.${this.instanceName}.togglePopover('${c.key}')">+</button>`;

        if (this.openPopoverKey === c.key) {
          const singleOp = schemaField.operators.length === 1;
          const applyCall = `window.${this.instanceName}.applyFilter('${c.key}', document.getElementById('popop_${c.key}').value, document.getElementById('popval_${c.key}').value, '${c.label}')`;

          let operatorHTML = '';
          if (singleOp) {
            const op = schemaField.operators[0];
            operatorHTML = `
              <div class="filter-op-label">${OP_LABELS[op] || op}</div>
              <input type="hidden" id="popop_${c.key}" value="${op}">
            `;
          } else {
            const operatorOptions = schemaField.operators.map(op =>
              `<option value="${op}">${OP_LABELS[op] || op}</option>`
            ).join('');
            operatorHTML = `
              <div class="select-wrapper">
                <select id="popop_${c.key}" class="form-input form-input--sm">${operatorOptions}</select>
              </div>
            `;
          }

          let inputHTML = '';
          if (schemaField.type === 'enum' && schemaField.options) {
            const opts = schemaField.options.map(o => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('');
            inputHTML = `
              <div class="select-wrapper">
                <select id="popval_${c.key}" class="form-input form-input--sm">${opts}</select>
              </div>
            `;
          } else {
            let inputType = 'text';
            if (schemaField.type === 'number') inputType = 'number';
            if (schemaField.type === 'date') inputType = 'date';
            inputHTML = `<input id="popval_${c.key}" type="${inputType}" class="form-input form-input--sm" placeholder="Значение…"
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

    const rowsHTML = data.items.map((item, idx) => {
      const cells = visibleCols.map(c => `<td>${c.render ? c.render(item, idx, data.items) : esc(item[c.key])}</td>`).join('');
      return `<tr>${cells}</tr>`;
    }).join('') || `<tr><td colspan="${visibleCols.length}" style="text-align:center; color:var(--color-text-muted); padding:24px;">${this.emptyText}</td></tr>`;

    const pages = Math.max(1, Math.ceil(data.total / this.state.limit));
    const isFirst = this.state.page <= 1;
    const isLast = this.state.page >= pages;

    const columnsConfigHTML = `
      <div style="position:relative;">
        <button class="btn btn--ghost btn--sm" onclick="event.stopPropagation(); window.${this.instanceName}.toggleConfig()">Колонки</button>
        ${this.configOpen ? `
          <div class="filter-popover" style="position:absolute; right:0; left:auto; top:calc(100% + 8px); padding:16px; min-width:200px; z-index:9999; max-height:350px; overflow-y:auto;">
            <div class="filter-popover__title" style="margin-bottom:12px;">Видимые колонки</div>
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${this.columns.map(c => `
                <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:13px;">
                  <input type="checkbox" ${c.visible ? 'checked' : ''} onchange="window.${this.instanceName}.toggleColumn('${c.key}')">
                  ${esc(c.label)}
                </label>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    `;

    const topControlsHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; flex-wrap:wrap;">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:13px; color:var(--color-text-muted);">Показывать:</span>
            <select class="form-input form-input--sm" style="width:auto;" onchange="window.${this.instanceName}.setLimit(this.value)">
              <option value="10" ${this.state.limit === 10 ? 'selected' : ''}>10</option>
              <option value="20" ${this.state.limit === 20 ? 'selected' : ''}>20</option>
              <option value="50" ${this.state.limit === 50 ? 'selected' : ''}>50</option>
            </select>
          </div>
          ${columnsConfigHTML}
        </div>
        <div style="display:flex; align-items:center; gap:4px;">
          <button class="btn btn--ghost btn--sm" ${isFirst ? 'disabled' : ''} onclick="window.${this.instanceName}.setPage(1)">&laquo;</button>
          <button class="btn btn--ghost btn--sm" ${isFirst ? 'disabled' : ''} onclick="window.${this.instanceName}.setPage(${this.state.page - 1})">&lsaquo;</button>
          <span style="font-size:13px; color:var(--color-text-muted); display:flex; align-items:center; gap:6px; margin:0 4px;">
            стр.
            <input type="number" class="form-input form-input--sm" style="width:50px; text-align:center;" value="${this.state.page}" min="1" max="${pages}" onchange="window.${this.instanceName}.setPage(this.value)">
            из ${pages} &nbsp;·&nbsp; всего: ${data.total}
          </span>
          <button class="btn btn--ghost btn--sm" ${isLast ? 'disabled' : ''} onclick="window.${this.instanceName}.setPage(${this.state.page + 1})">&rsaquo;</button>
          <button class="btn btn--ghost btn--sm" ${isLast ? 'disabled' : ''} onclick="window.${this.instanceName}.setPage(${pages})">&raquo;</button>
        </div>
      </div>
    `;

    this.container.innerHTML = `
      ${activeFiltersHTML ? `<div class="active-filters">${activeFiltersHTML}</div>` : ''}
      ${topControlsHTML}
      <div style="border:1px solid var(--color-border); border-radius:var(--radius); overflow:hidden;">
        <table class="table">
          <thead><tr>${headers}</tr></thead>
          <tbody>${rowsHTML}</tbody>
        </table>
      </div>
    `;
  }
}
