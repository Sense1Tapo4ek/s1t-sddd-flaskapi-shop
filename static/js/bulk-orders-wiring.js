/* Bulk Action Bar wiring for the orders table.
   Used by:
   - src/ordering/templates/ordering/pages/orders.html (window.ordersTable)
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

  // ─── Order status picker modal ──────────────────────────────────────
  // Returns a Promise resolving to one of "new" | "processing" | "done" |
  // "canceled" or null if the user cancelled.

  const ORDER_STATUS_OPTIONS = [
    { value: "new",        label: "Новый" },
    { value: "processing", label: "В обработке" },
    { value: "done",       label: "Выполнен" },
    { value: "canceled",   label: "Отменён" },
  ];

  function pickOrderStatusModal() {
    return new Promise(resolve => {
      const optionsHtml = ORDER_STATUS_OPTIONS.map(opt => `
        <label style="display:block; padding:8px 10px; cursor:pointer; border-radius:var(--radius);">
          <input type="radio" name="bulkOrderStatus" value="${escapeHTML(opt.value)}" style="margin-right:8px;">
          ${escapeHTML(opt.label)}
        </label>
      `).join("");

      const html = `
        <div class="modal-overlay modal-overlay--active" id="bulkOrderStatusOverlay" role="dialog" aria-modal="true">
          <div class="modal">
            <div class="modal__header">
              Изменить статус заказов
              <button class="modal__close" type="button" data-role="close">&times;</button>
            </div>
            <div class="modal__body">
              <p style="font-size:13px; color:var(--color-text-muted); margin:0 0 12px;">
                Выберите новый статус для выбранных заказов.
              </p>
              <div id="bulkOrderStatusList" style="border:1px solid var(--color-border); border-radius:var(--radius); padding:4px;">
                ${optionsHtml}
              </div>
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

      const confirmBtn = overlay.querySelector('[data-role="confirm"]');
      let selectedStatus = null;

      overlay.addEventListener("change", e => {
        if (e.target && e.target.name === "bulkOrderStatus") {
          selectedStatus = e.target.value;
          confirmBtn.disabled = false;
        }
      });

      const close = (result) => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
        resolve(result);
      };
      const onKey = (e) => {
        if (e.key === "Escape") close(null);
        else if (e.key === "Enter" && !confirmBtn.disabled) {
          if (selectedStatus != null) close(selectedStatus);
        }
      };

      overlay.querySelector('[data-role="cancel"]').addEventListener("click", () => close(null));
      overlay.querySelector('[data-role="close"]').addEventListener("click", () => close(null));
      overlay.addEventListener("click", e => { if (e.target === overlay) close(null); });
      confirmBtn.addEventListener("click", () => {
        if (selectedStatus == null) return;
        close(selectedStatus);
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

  function mountOrdersBulkBar(table) {
    if (!table) return null;
    return new global.BulkActionBar({
      table: table,
      getRowName: o => "Заказ #" + o.id,
      actions: [
        {
          id: "status",
          label: "Изменить статус",
          icon: "arrow-right-circle",
          confirm: "none",
          handler: async (payload) => {
            const status = await global.bulkPickOrderStatus();
            if (status == null) return { cancelled: true };
            return postBulk("/admin/orders/bulk/status",
              { ...payload, status: status });
          }
        }
      ]
    });
  }

  global.mountOrdersBulkBar = mountOrdersBulkBar;
  global.bulkPickOrderStatus = pickOrderStatusModal;
})(window);
