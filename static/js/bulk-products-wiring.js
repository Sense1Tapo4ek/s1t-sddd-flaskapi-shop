/* Bulk Action Bar wiring for product tables.
   Used by:
   - static/templates/catalog/pages/products.html (window.productsTable)
   - static/js/catalog-workspace.js (state.categoryProductsTable)
   Spec: docs/superpowers/specs/2026-05-15-bulk-actions-design.md §4.
*/

(function (global) {
  "use strict";

  function escapeHTML(s) {
    if (typeof global.esc === "function") return global.esc(s);
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmtNum(n) {
    return (typeof global.bulkFmtNumber === "function") ? global.bulkFmtNumber(n) : String(n);
  }

  // ─── Category picker modal ──────────────────────────────────────────
  // Returns a Promise resolving to a leaf category_id (number) or null
  // if the user cancelled.

  function flattenLeafCategories(nodes, depth, out) {
    if (!Array.isArray(nodes)) return;
    nodes.forEach(node => {
      const hasChildren = Array.isArray(node.children) && node.children.length > 0;
      out.push({ id: node.id, title: node.title, depth: depth, isLeaf: !hasChildren });
      if (hasChildren) flattenLeafCategories(node.children, depth + 1, out);
    });
  }

  async function pickCategoryModal() {
    const tree = await global.api.get("/catalog/admin/categories/tree");
    if (!tree || tree._failed) return null;

    const flat = [];
    flattenLeafCategories(tree, 0, flat);

    return new Promise(resolve => {
      const html = `
        <div class="modal-overlay modal-overlay--active" id="bulkCategoryOverlay" role="dialog" aria-modal="true">
          <div class="modal">
            <div class="modal__header">
              Назначить категорию
              <button class="modal__close" type="button" data-role="close">&times;</button>
            </div>
            <div class="modal__body">
              <p style="font-size:13px; color:var(--color-text-muted); margin:0 0 12px;">
                Выберите конечную категорию. Неконечные категории (с подкатегориями) недоступны.
              </p>
              <input type="text" class="form-input" id="bulkCategorySearch" placeholder="Поиск…" autocomplete="off" style="margin-bottom:8px;">
              <div id="bulkCategoryList" style="max-height:50vh; overflow-y:auto; border:1px solid var(--color-border); border-radius:var(--radius); padding:4px;"></div>
            </div>
            <div class="modal__footer">
              <button type="button" class="btn btn--ghost" data-role="cancel">Отмена</button>
              <button type="button" class="btn btn--primary" data-role="confirm" disabled>Назначить</button>
            </div>
          </div>
        </div>
      `;
      const host = document.createElement("div");
      host.innerHTML = html;
      const overlay = host.firstElementChild;
      document.body.appendChild(overlay);

      const listEl = overlay.querySelector("#bulkCategoryList");
      const searchEl = overlay.querySelector("#bulkCategorySearch");
      const confirmBtn = overlay.querySelector('[data-role="confirm"]');
      let selectedId = null;

      function renderList(query) {
        const q = (query || "").trim().toLowerCase();
        const items = flat
          .filter(c => !q || c.title.toLowerCase().includes(q))
          .map(c => {
            const pad = 8 + c.depth * 16;
            const disabled = !c.isLeaf;
            const isSel = c.id === selectedId;
            return `
              <div class="bulk-cat-item${disabled ? ' is-disabled' : ''}${isSel ? ' is-selected' : ''}"
                   data-cat-id="${c.id}" data-leaf="${c.isLeaf ? '1' : '0'}"
                   style="padding:6px 8px 6px ${pad}px; cursor:${disabled ? 'not-allowed' : 'pointer'}; color:${disabled ? 'var(--color-text-muted)' : 'inherit'}; background:${isSel ? 'var(--color-bg-soft, #f4f5f1)' : 'transparent'}; border-radius:var(--radius);">
                ${escapeHTML(c.title)}${disabled ? ' <span style="font-size:11px;">(не конечная)</span>' : ''}
              </div>
            `;
          })
          .join("");
        listEl.innerHTML = items || '<p class="empty-text" style="margin:8px;">Ничего не найдено</p>';
      }
      renderList("");

      listEl.addEventListener("click", e => {
        const row = e.target.closest("[data-cat-id]");
        if (!row || row.dataset.leaf !== "1") return;
        selectedId = Number(row.dataset.catId);
        confirmBtn.disabled = false;
        renderList(searchEl.value);
      });
      searchEl.addEventListener("input", () => renderList(searchEl.value));

      const close = (result) => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
        resolve(result);
      };
      const onKey = (e) => { if (e.key === "Escape") close(null); };

      overlay.querySelector('[data-role="cancel"]').addEventListener("click", () => close(null));
      overlay.querySelector('[data-role="close"]').addEventListener("click", () => close(null));
      overlay.addEventListener("click", e => { if (e.target === overlay) close(null); });
      confirmBtn.addEventListener("click", () => {
        if (selectedId == null) return;
        close(selectedId);
      });
      document.addEventListener("keydown", onKey);
      setTimeout(() => searchEl.focus(), 30);
    });
  }

  // ─── Tags picker modal ──────────────────────────────────────────────
  // Returns a Promise resolving to { tag_ids: number[], mode: 'replace'|'add'|'remove' }
  // or null if the user cancelled.

  function pickTagsModal() {
    return new Promise(resolve => {
      const html = `
        <div class="modal-overlay modal-overlay--active" id="bulkTagsOverlay" role="dialog" aria-modal="true">
          <div class="modal">
            <div class="modal__header">
              Изменить теги
              <button class="modal__close" type="button" data-role="close">&times;</button>
            </div>
            <div class="modal__body">
              <fieldset style="border:none; padding:0; margin:0 0 12px;">
                <legend style="font-size:13px; color:var(--color-text-muted); margin-bottom:6px;">Режим</legend>
                <label style="margin-right:12px;"><input type="radio" name="bulkTagsMode" value="replace" checked> Заменить</label>
                <label style="margin-right:12px;"><input type="radio" name="bulkTagsMode" value="add"> Добавить</label>
                <label><input type="radio" name="bulkTagsMode" value="remove"> Убрать</label>
              </fieldset>
              <div id="bulkTagsPickerHost" class="tag-picker"></div>
            </div>
            <div class="modal__footer">
              <button type="button" class="btn btn--ghost" data-role="cancel">Отмена</button>
              <button type="button" class="btn btn--primary" data-role="confirm" disabled>Применить</button>
            </div>
          </div>
        </div>
      `;
      const host = document.createElement("div");
      host.innerHTML = html;
      const overlay = host.firstElementChild;
      document.body.appendChild(overlay);

      const pickerHost = overlay.querySelector("#bulkTagsPickerHost");
      const confirmBtn = overlay.querySelector('[data-role="confirm"]');
      const picker = new global.TagPicker({ container: pickerHost });
      picker.load([]).then(() => {
        pickerHost.addEventListener("change", () => {
          confirmBtn.disabled = picker.getValue().length === 0;
        });
      });

      const close = (result) => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
        resolve(result);
      };
      const onKey = (e) => { if (e.key === "Escape") close(null); };

      overlay.querySelector('[data-role="cancel"]').addEventListener("click", () => close(null));
      overlay.querySelector('[data-role="close"]').addEventListener("click", () => close(null));
      overlay.addEventListener("click", e => { if (e.target === overlay) close(null); });
      confirmBtn.addEventListener("click", () => {
        const tag_ids = picker.getValue();
        if (!tag_ids.length) return;
        const mode = overlay.querySelector('input[name="bulkTagsMode"]:checked').value;
        close({ tag_ids: tag_ids, mode: mode });
      });
      document.addEventListener("keydown", onKey);
    });
  }

  // Wraps an api.post call: api.js already shows an error toast on failure,
  // so a failed call should NOT trigger BulkActionBar's "success" path.
  async function postBulk(url, body) {
    const res = await global.api.post(url, body);
    if (res && res._failed) return { cancelled: true };
    return res;
  }

  // ─── Mount BulkActionBar on a SmartTable ────────────────────────────

  function mountProductsBulkBar(table) {
    if (!table) return null;
    return new global.BulkActionBar({
      table: table,
      getRowName: p => p.title,
      actions: [
        {
          id: "activate",
          label: "Активировать",
          icon: "check-circle",
          confirm: "soft",
          handler: payload => postBulk("/admin/products/bulk/activate",
            { ...payload, active: true })
        },
        {
          id: "deactivate",
          label: "Деактивировать",
          icon: "circle-off",
          confirm: "soft",
          handler: payload => postBulk("/admin/products/bulk/activate",
            { ...payload, active: false })
        },
        {
          id: "category",
          label: "Категория",
          icon: "folder",
          confirm: "none",
          handler: async (payload) => {
            const categoryId = await pickCategoryModal();
            if (categoryId == null) return { cancelled: true };
            return postBulk("/admin/products/bulk/category",
              { ...payload, category_id: categoryId });
          }
        },
        {
          id: "tags",
          label: "Теги",
          icon: "tag",
          confirm: "none",
          handler: async (payload) => {
            const choice = await pickTagsModal();
            if (!choice) return { cancelled: true };
            return postBulk("/admin/products/bulk/tags",
              { ...payload, tag_ids: choice.tag_ids, mode: choice.mode });
          }
        },
        {
          id: "delete",
          label: "Удалить",
          icon: "trash-2",
          variant: "danger",
          confirm: "type-to-confirm",
          typeWord: "удалить",
          confirmTitle: "Удалить выбранные товары?",
          confirmText: sel => `Будет удалено: ${fmtNum(sel.total)}. Действие необратимо.`,
          handler: payload => postBulk("/admin/products/bulk/delete", payload)
        }
      ]
    });
  }

  global.mountProductsBulkBar = mountProductsBulkBar;
  global.bulkPickCategory = pickCategoryModal;
  global.bulkPickTags = pickTagsModal;
})(window);
