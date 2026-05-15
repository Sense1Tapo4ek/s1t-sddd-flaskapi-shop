/* Bulk Action Bar wiring for the tags table.
   Used by:
   - static/js/catalog-workspace.js (state.tagsTable)
   Spec: docs/superpowers/specs/2026-05-15-bulk-actions-design.md §4.
*/

(function (global) {
  "use strict";

  function fmtNum(n) {
    return (typeof global.bulkFmtNumber === "function") ? global.bulkFmtNumber(n) : String(n);
  }

  // Wraps an api.post call: api.js already shows an error toast on failure,
  // so a failed call should NOT trigger BulkActionBar's "success" path.
  async function postBulk(url, body) {
    const res = await global.api.post(url, body);
    if (res && res._failed) return { cancelled: true };
    return res;
  }

  // ─── Mount BulkActionBar on a SmartTable ────────────────────────────

  function mountTagsBulkBar(table) {
    if (!table) return null;
    return new global.BulkActionBar({
      table: table,
      getRowName: t => t.title,
      actions: [
        {
          id: "activate",
          label: "Активировать",
          icon: "check-circle",
          confirm: "soft",
          handler: payload => postBulk("/admin/tags/bulk/activate",
            { ...payload, active: true })
        },
        {
          id: "deactivate",
          label: "Деактивировать",
          icon: "circle-off",
          confirm: "soft",
          handler: payload => postBulk("/admin/tags/bulk/activate",
            { ...payload, active: false })
        },
        {
          id: "delete",
          label: "Удалить",
          icon: "trash-2",
          variant: "danger",
          confirm: "type-to-confirm",
          typeWord: "удалить",
          confirmTitle: "Удалить выбранные теги?",
          confirmText: sel => `Будет удалено: ${fmtNum(sel.total)}. Действие необратимо.`,
          handler: payload => postBulk("/admin/tags/bulk/delete", payload)
        }
      ]
    });
  }

  global.mountTagsBulkBar = mountTagsBulkBar;
})(window);
