/* Bulk Action Bar wiring for the orders table.
   Used by:
   - src/ordering/templates/ordering/pages/orders.html (window.ordersTable)
   Spec: docs/superpowers/specs/2026-05-15-bulk-actions-design.md §4.

   The status picker is mounted inside the unified action modal via
   `customControls` — no separate picker overlay.
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

  const ORDER_STATUS_OPTIONS = [
    { value: "new",        i18n: "bulk.orders.status.new" },
    { value: "processing", i18n: "bulk.orders.status.processing" },
    { value: "done",       i18n: "bulk.orders.status.done" },
    { value: "canceled",   i18n: "bulk.orders.status.canceled" },
  ];

  function statusControls() {
    const state = { status: null };
    const optionsHtml = ORDER_STATUS_OPTIONS.map(opt => `
      <label style="display:block; padding:6px 4px;">
        <input type="radio" name="bulkOrderStatus" value="${escapeHTML(opt.value)}">
        ${escapeHTML(bulkT(opt.i18n))}
      </label>
    `).join("");
    const html = `
      <fieldset>
        <legend>${escapeHTML(bulkT("bulk.orders.modal.statusLegend"))}</legend>
        ${optionsHtml}
      </fieldset>
    `;
    return {
      html: html,
      onMount: (overlay, ctx) => {
        ctx.setValid(false);
        overlay.addEventListener("change", e => {
          if (e.target && e.target.name === "bulkOrderStatus") {
            state.status = e.target.value;
            ctx.setValid(true);
          }
        });
      },
      validate: () => state.status != null,
      getValue: () => ({ status: state.status }),
    };
  }

  async function postBulk(url, body) {
    const res = await global.api.post(url, body);
    if (res && res._failed) return { cancelled: true };
    return res;
  }

  function mountOrdersBulkBar(table) {
    if (!table) return null;
    return new global.BulkActionBar({
      table: table,
      getRowName: o => "Заказ #" + o.id,
      actions: [
        {
          id: "status",
          label: bulkT("bulk.orders.action.status"),
          icon: "arrow-right-circle",
          confirm: "modal",
          explain: () => bulkT("bulk.orders.explain.status"),
          customControls: () => statusControls(),
          handler: payload => postBulk("/admin/orders/bulk/status", payload)
        }
      ]
    });
  }

  global.mountOrdersBulkBar = mountOrdersBulkBar;
})(window);
