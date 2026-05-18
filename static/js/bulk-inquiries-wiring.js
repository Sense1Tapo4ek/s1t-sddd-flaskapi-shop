/* Bulk Action Bar wiring for the inquiries table.
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

  const INQUIRY_STATUS_OPTIONS = [
    { value: "new",         i18n: "bulk.inquiries.status.new" },
    { value: "in_progress", i18n: "bulk.inquiries.status.in_progress" },
    { value: "closed",      i18n: "bulk.inquiries.status.closed" },
    { value: "archived",    i18n: "bulk.inquiries.status.archived" },
  ];

  function statusControls() {
    const state = { status: null };
    const optionsHtml = INQUIRY_STATUS_OPTIONS.map(opt => `
      <label style="display:block; padding:6px 4px;">
        <input type="radio" name="bulkInquiryStatus" value="${escapeHTML(opt.value)}">
        ${escapeHTML(bulkT(opt.i18n))}
      </label>
    `).join("");
    const html = `
      <fieldset>
        <legend>${escapeHTML(bulkT("bulk.inquiries.modal.statusLegend"))}</legend>
        ${optionsHtml}
      </fieldset>
    `;
    return {
      html: html,
      onMount: (overlay, ctx) => {
        ctx.setValid(false);
        overlay.addEventListener("change", e => {
          if (e.target && e.target.name === "bulkInquiryStatus") {
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

  function mountInquiriesBulkBar(table) {
    if (!table) return null;
    return new global.BulkActionBar({
      table: table,
      getRowName: o => "Обращение #" + o.id,
      actions: [
        {
          id: "status",
          label: bulkT("bulk.inquiries.action.status"),
          icon: "arrow-right-circle",
          confirm: "modal",
          explain: () => bulkT("bulk.inquiries.explain.status"),
          customControls: () => statusControls(),
          handler: payload => postBulk("/admin/inquiries/bulk/status", payload)
        },
        {
          id: "archive",
          label: bulkT("bulk.inquiries.action.archive"),
          icon: "archive",
          confirm: "toast",
          explain: () => bulkT("bulk.inquiries.explain.archive"),
          handler: payload => postBulk("/admin/inquiries/bulk/archive", payload)
        }
      ]
    });
  }

  global.mountInquiriesBulkBar = mountInquiriesBulkBar;
})(window);
