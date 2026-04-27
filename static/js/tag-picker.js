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

  class TagPicker {
    constructor(options) {
      this.container = typeof options.containerId === 'string'
        ? document.getElementById(options.containerId)
        : options.container;
      this.endpoint = options.endpoint || '/catalog/admin/tags';
      this.selectedIds = new Set((options.selectedIds || []).map(Number));
      this.tags = [];
      if (this.container) {
        this.container.addEventListener('change', event => {
          const input = event.target.closest('[data-tag-id]');
          if (!input) return;
          const id = Number(input.dataset.tagId);
          if (input.checked) this.selectedIds.add(id);
          else this.selectedIds.delete(id);
        });
      }
    }

    async load(selectedIds) {
      if (selectedIds) this.selectedIds = new Set(selectedIds.map(Number));
      const response = await api.get(this.endpoint);
      this.tags = Array.isArray(response) ? response : (response.items || []);
      this.render();
    }

    getValue() {
      return Array.from(this.selectedIds);
    }

    render() {
      if (!this.container) return;
      if (!this.tags.length) {
        this.container.innerHTML = '<p class="empty-text">Теги не созданы</p>';
        return;
      }
      this.container.innerHTML = this.tags.map(tag => `
        <label class="tag-picker__item">
          <input type="checkbox" data-tag-id="${tag.id}" ${this.selectedIds.has(Number(tag.id)) ? 'checked' : ''}>
          <span class="tag-picker__swatch" style="background:${escapeHtml(tag.color || '#7c8c6e')}"></span>
          <span>${escapeHtml(tag.title)}</span>
        </label>
      `).join('');
    }
  }

  window.TagPicker = TagPicker;
})();
