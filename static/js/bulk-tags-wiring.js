/* Bulk Action Bar wiring for the tags table.
   Used by:
   - static/js/catalog-workspace.js (state.tagsTable)
   Spec: docs/superpowers/specs/2026-05-15-bulk-actions-design.md §4.

   Every action uses the unified modal flow — no soft-arm, no
   type-to-confirm. Destructive Delete gets a red primary button via
   `variant: "danger"`.
*/

(function (global) {
  "use strict";

  function bulkT(key, params) {
    return (typeof global.bulkT === "function") ? global.bulkT(key, params) : key;
  }

  async function postBulk(url, body) {
    const res = await global.api.post(url, body);
    if (res && res._failed) return { cancelled: true };
    return res;
  }

  function mountTagsBulkBar(table) {
    if (!table) return null;
    return new global.BulkActionBar({
      table: table,
      getRowName: t => t.title,
      actions: [
        {
          id: "activate",
          label: bulkT("bulk.btn.activate"),
          icon: "check-circle",
          confirm: "modal",
          explain: () => bulkT("bulk.tags.explain.activate"),
          handler: payload => postBulk("/admin/tags/bulk/activate",
            { ...payload, active: true })
        },
        {
          id: "deactivate",
          label: bulkT("bulk.btn.deactivate"),
          icon: "circle-off",
          confirm: "modal",
          explain: () => bulkT("bulk.tags.explain.deactivate"),
          handler: payload => postBulk("/admin/tags/bulk/activate",
            { ...payload, active: false })
        },
        {
          id: "delete",
          label: bulkT("bulk.btn.delete"),
          icon: "trash-2",
          variant: "danger",
          confirm: "modal",
          explain: sel => bulkT("bulk.tags.confirm.deleteText", { n: sel.total }),
          handler: payload => postBulk("/admin/tags/bulk/delete", payload)
        }
      ]
    });
  }

  global.mountTagsBulkBar = mountTagsBulkBar;
})(window);
