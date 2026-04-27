(function() {
  'use strict';

  function escapeHtml(value) {
    if (typeof esc === 'function') return esc(value);
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  class AttributeForm {
    constructor(options) {
      this.container = typeof options.containerId === 'string'
        ? document.getElementById(options.containerId)
        : options.container;
      this.categoryId = null;
      this.attributes = [];
      this.values = {};
    }

    async load(categoryId, values) {
      this.categoryId = categoryId ? Number(categoryId) : null;
      this.values = values || {};
      if (!this.container) return;
      if (!this.categoryId) {
        this.container.innerHTML = '<p class="form-hint">Выберите категорию, чтобы заполнить атрибуты.</p>';
        return;
      }
      const response = await api.get(`/catalog/admin/categories/${this.categoryId}/attributes`);
      this.attributes = response.items || [];
      this.render();
    }

    getValue() {
      const result = {};
      if (!this.container) return result;
      this.attributes.forEach(attr => {
        const controls = this.container.querySelectorAll(`[data-attr-code="${CSS.escape(attr.code)}"]`);
        if (!controls.length) return;
        if (attr.type === 'boolean') {
          result[attr.code] = controls[0].checked;
        } else if (attr.type === 'multiselect') {
          result[attr.code] = Array.from(controls).filter(c => c.checked).map(c => c.value);
        } else if (['file', 'image'].includes(attr.type) && attr.value_mode === 'multiple') {
          result[attr.code] = controls[0].value
            .replace(/\n/g, ',')
            .split(',')
            .map(item => item.trim())
            .filter(Boolean);
        } else {
          result[attr.code] = controls[0].value;
        }
      });
      return result;
    }

    render() {
      if (!this.container) return;
      if (!this.attributes.length) {
        this.container.innerHTML = '<p class="form-hint">У категории нет атрибутов.</p>';
        return;
      }
      this.container.innerHTML = this.attributes.map(attr => this.renderAttribute(attr)).join('');
    }

    renderAttribute(attr) {
      const required = attr.is_required && attr.type !== 'date' ? 'required' : '';
      const label = `${escapeHtml(attr.title)}${attr.is_required ? ' *' : ''}${attr.unit ? ' (' + escapeHtml(attr.unit) + ')' : ''}`;
      const value = this.values[attr.code];
      let control = '';
      if (attr.type === 'boolean') {
        control = `<label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" data-attr-code="${escapeHtml(attr.code)}" ${value ? 'checked' : ''}> <span>Да</span></label>`;
      } else if (attr.type === 'select') {
        control = `<select class="form-input" data-attr-code="${escapeHtml(attr.code)}" ${required}>
          <option value="">—</option>
          ${(attr.options || []).map(o => `<option value="${escapeHtml(o.value)}" ${String(value || '') === String(o.value) ? 'selected' : ''}>${escapeHtml(o.label)}</option>`).join('')}
        </select>`;
      } else if (attr.type === 'multiselect') {
        const values = Array.isArray(value) ? value : [];
        control = `<div class="tag-picker">${(attr.options || []).map(o => `
          <label class="tag-picker__item">
            <input type="checkbox" data-attr-code="${escapeHtml(attr.code)}" value="${escapeHtml(o.value)}" ${values.includes(o.value) ? 'checked' : ''}>
            <span>${escapeHtml(o.label)}</span>
          </label>
        `).join('')}</div>`;
      } else if (['file', 'image'].includes(attr.type) && attr.value_mode === 'multiple') {
        const values = Array.isArray(value) ? value.join('\n') : value || '';
        control = `<textarea class="form-input form-textarea" data-attr-code="${escapeHtml(attr.code)}" ${required}>${escapeHtml(values)}</textarea>`;
      } else {
        const inputType = attr.type === 'number' ? 'number' : attr.type === 'date' ? 'date' : attr.type === 'url' ? 'url' : 'text';
        control = `<input class="form-input" type="${inputType}" data-attr-code="${escapeHtml(attr.code)}" value="${escapeHtml(value || '')}" ${required}>`;
      }
      return `<div class="form-group"><label class="form-label">${label}</label>${control}</div>`;
    }
  }

  window.AttributeForm = AttributeForm;
})();
