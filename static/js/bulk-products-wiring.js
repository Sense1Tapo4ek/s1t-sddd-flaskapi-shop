/* Bulk Action Bar wiring for product tables.
   Used by:
   - static/templates/catalog/pages/products.html (window.productsTable)
   - static/js/catalog-workspace.js (state.categoryProductsTable)
   Spec: docs/superpowers/specs/2026-05-15-bulk-actions-design.md §4.

   Every action uses the unified modal flow (see BulkActionBar
   `_openActionModal`): each action descriptor supplies `explain(sel)`
   plain text and, when an extra choice is needed (category/tags),
   `customControls(sel)` mounting a picker inside the same modal.
*/

(function (global) {
  "use strict";

  function escapeHTML(s) {
    if (typeof global.esc === "function") return global.esc(s);
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function bulkT(key, params) {
    return (typeof global.bulkT === "function") ? global.bulkT(key, params) : key;
  }

  // ─── Category picker controls (mounted into the unified modal) ──────

  function flattenLeafCategories(nodes, depth, out) {
    if (!Array.isArray(nodes)) return;
    nodes.forEach(node => {
      const hasChildren = Array.isArray(node.children) && node.children.length > 0;
      out.push({ id: node.id, title: node.title, depth: depth, isLeaf: !hasChildren });
      if (hasChildren) flattenLeafCategories(node.children, depth + 1, out);
    });
  }

  function categoryControls() {
    const state = { selectedId: null, flat: [] };
    const html = `
      <input type="text" class="form-input" data-role="cat-search"
             placeholder="${escapeHTML(bulkT("bulk.products.modal.category.search"))}"
             autocomplete="off" style="margin-bottom:8px;">
      <div data-role="cat-list" class="bulk-cat-list"
           style="max-height:40vh; overflow-y:auto; border:1px solid var(--color-border); border-radius:var(--radius); padding:4px;">
        <p class="empty-text" style="margin:8px;">${escapeHTML(bulkT("bulk.products.modal.category.help"))}</p>
      </div>
    `;
    function renderList(overlay) {
      const listEl = overlay.querySelector('[data-role="cat-list"]');
      const searchEl = overlay.querySelector('[data-role="cat-search"]');
      const q = (searchEl.value || "").trim().toLowerCase();
      const items = state.flat
        .filter(c => !q || c.title.toLowerCase().includes(q))
        .map(c => {
          const pad = 8 + c.depth * 16;
          const disabled = !c.isLeaf;
          const isSel = c.id === state.selectedId;
          const notLeaf = bulkT("bulk.products.modal.category.notLeaf");
          return `
            <div class="bulk-cat-item${disabled ? ' is-disabled' : ''}${isSel ? ' is-selected' : ''}"
                 data-cat-id="${c.id}" data-leaf="${c.isLeaf ? '1' : '0'}"
                 style="padding:6px 8px 6px ${pad}px; cursor:${disabled ? 'not-allowed' : 'pointer'}; color:${disabled ? 'var(--color-text-muted)' : 'inherit'}; background:${isSel ? 'var(--color-bg-soft, #f4f5f1)' : 'transparent'}; border-radius:var(--radius);">
              ${escapeHTML(c.title)}${disabled ? ` <span style="font-size:11px;">(${escapeHTML(notLeaf)})</span>` : ""}
            </div>
          `;
        })
        .join("");
      listEl.innerHTML = items || `<p class="empty-text" style="margin:8px;">${escapeHTML(bulkT("bulk.empty.notFound"))}</p>`;
    }
    return {
      html: html,
      onMount: (overlay, ctx) => {
        ctx.setValid(false);
        global.api.get("/catalog/admin/categories/tree").then(tree => {
          if (!tree || tree._failed) return;
          state.flat = [];
          flattenLeafCategories(tree, 0, state.flat);
          renderList(overlay);
        });
        const searchEl = overlay.querySelector('[data-role="cat-search"]');
        const listEl = overlay.querySelector('[data-role="cat-list"]');
        searchEl.addEventListener("input", () => renderList(overlay));
        listEl.addEventListener("click", e => {
          const row = e.target.closest("[data-cat-id]");
          if (!row || row.dataset.leaf !== "1") return;
          state.selectedId = Number(row.dataset.catId);
          renderList(overlay);
          ctx.setValid(true);
        });
      },
      validate: () => state.selectedId != null,
      getValue: () => ({ category_id: state.selectedId }),
    };
  }

  // ─── Tags picker controls ───────────────────────────────────────────

  function tagsControls() {
    const state = { mode: "add", tagIds: [], picker: null };
    const html = `
      <fieldset>
        <legend>${escapeHTML(bulkT("bulk.products.modal.tags.modeLegend"))}</legend>
        <label><input type="radio" name="bulkTagsMode" value="add" checked> ${escapeHTML(bulkT("bulk.products.modal.tags.mode.add"))}</label>
        <label><input type="radio" name="bulkTagsMode" value="remove"> ${escapeHTML(bulkT("bulk.products.modal.tags.mode.remove"))}</label>
        <label><input type="radio" name="bulkTagsMode" value="replace"> ${escapeHTML(bulkT("bulk.products.modal.tags.mode.replace"))}</label>
      </fieldset>
      <div data-role="tags-picker" class="tag-picker"></div>
    `;
    function refresh(overlay, ctx) {
      const valid = state.tagIds.length > 0;
      const danger = state.mode === "replace";
      ctx.setValid({ valid: valid, danger: danger });
    }
    return {
      html: html,
      onMount: (overlay, ctx) => {
        const pickerHost = overlay.querySelector('[data-role="tags-picker"]');
        state.picker = new global.TagPicker({ container: pickerHost });
        state.picker.load([]).then(() => {
          pickerHost.addEventListener("change", () => {
            state.tagIds = state.picker.getValue();
            refresh(overlay, ctx);
          });
        });
        overlay.querySelectorAll('input[name="bulkTagsMode"]').forEach(input => {
          input.addEventListener("change", () => {
            state.mode = overlay.querySelector('input[name="bulkTagsMode"]:checked').value;
            refresh(overlay, ctx);
          });
        });
        ctx.setValid({ valid: false, danger: false });
      },
      validate: () => state.tagIds.length > 0,
      getValue: () => ({ tag_ids: state.tagIds, mode: state.mode }),
    };
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
          label: bulkT("bulk.btn.activate"),
          icon: "check-circle",
          confirm: "modal",
          explain: () => bulkT("bulk.products.explain.activate"),
          handler: payload => postBulk("/admin/products/bulk/activate",
            { ...payload, active: true })
        },
        {
          id: "deactivate",
          label: bulkT("bulk.btn.deactivate"),
          icon: "circle-off",
          confirm: "modal",
          explain: () => bulkT("bulk.products.explain.deactivate"),
          handler: payload => postBulk("/admin/products/bulk/activate",
            { ...payload, active: false })
        },
        {
          id: "category",
          label: bulkT("bulk.products.action.category"),
          icon: "folder",
          confirm: "modal",
          explain: () => bulkT("bulk.products.explain.category"),
          customControls: () => categoryControls(),
          handler: payload => postBulk("/admin/products/bulk/category", payload)
        },
        {
          id: "tags",
          label: bulkT("bulk.products.action.tags"),
          icon: "tag",
          confirm: "modal",
          // Explain swaps by mode at modal-open time. Mode picker also
          // recolors the primary button to red when "replace" is chosen.
          explain: () => bulkT("bulk.products.explain.tags.add"),
          customControls: () => tagsControls(),
          handler: payload => postBulk("/admin/products/bulk/tags", payload)
        },
        {
          id: "delete",
          label: bulkT("bulk.btn.delete"),
          icon: "trash-2",
          variant: "danger",
          confirm: "modal",
          explain: sel => bulkT("bulk.products.confirm.deleteText", { n: sel.total }),
          handler: payload => postBulk("/admin/products/bulk/delete", payload)
        }
      ]
    });
  }

  global.mountProductsBulkBar = mountProductsBulkBar;
})(window);
