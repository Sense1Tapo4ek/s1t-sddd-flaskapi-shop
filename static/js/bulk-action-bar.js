/* Bulk Action Bar — floating capsule that surfaces actions on the
   current SmartTable selection.
   Spec: docs/superpowers/specs/2026-05-15-bulk-actions-design.md §4.2, §10. */

(function (global) {
  "use strict";

  const SOFT_CONFIRM_TIMEOUT = 3000;
  const FOCUS_DELAY_MS = 30;        // one paint cycle before focusing a freshly mounted modal input

  function bulkText(key, params) {
    return (typeof global.bulkT === "function") ? global.bulkT(key, params) : key;
  }

  function bulkReason(code) {
    return (typeof global.bulkReason === "function") ? global.bulkReason(code) : code;
  }

  function fmtNum(n) {
    return (typeof global.bulkFmtNumber === "function") ? global.bulkFmtNumber(n) : String(n);
  }

  function escapeHTML(s) {
    if (typeof global.esc === "function") return global.esc(s);
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function iconSvg(name, extraClass) {
    const cls = "lucide" + (extraClass ? " " + extraClass : "");
    return `<svg class="${cls}" aria-hidden="true"><use href="/static/img/lucide.svg#icon-${escapeHTML(name)}"/></svg>`;
  }

  class BulkActionBar {
    constructor({ table, actions, container, getRowName, countLabel }) {
      this.table = table;
      this.actions = Array.isArray(actions) ? actions : [];
      this.container = container || document.body;
      this.getRowName = typeof getRowName === "function" ? getRowName : null;
      this.countLabel = typeof countLabel === "function" ? countLabel : null;

      this.el = null;
      this.softArmed = null;  // {actionId, timer}
      this.busy = false;
      this._prevCount = 0;

      this._render();
      this._installBeforeUnloadGuard();

      // Subscribe to selection changes.
      if (this.table) {
        const prev = this.table.onSelectionChange;
        this.table.onSelectionChange = (sel) => {
          if (typeof prev === "function") prev(sel);
          this.update(sel);
        };
        // Inject getRowName if not set on the table.
        if (this.getRowName && !this.table.getRowName) {
          this.table.getRowName = this.getRowName;
        }
      }
    }

    _installBeforeUnloadGuard() {
      this._onBeforeUnload = (e) => {
        if (!this.busy) return undefined;
        const msg = bulkText("bulk.beforeUnload");
        e.preventDefault();
        e.returnValue = msg;
        return msg;
      };
      window.addEventListener("beforeunload", this._onBeforeUnload);
    }

    destroy() {
      window.removeEventListener("beforeunload", this._onBeforeUnload);
      if (this.softArmed) clearTimeout(this.softArmed.timer);
      if (this.el) this.el.remove();
      document.body.classList.remove("has-bulk-bar");
    }

    _render() {
      const el = document.createElement("div");
      el.className = "bulk-bar";
      el.setAttribute("role", "region");
      el.setAttribute("aria-label", "Массовые действия");
      el.innerHTML = `
        <div class="bulk-bar__count">
          <span class="bulk-bar__dot"></span>
          <span class="bulk-bar__count-num" data-role="count">0</span>
        </div>
        <div class="bulk-bar__actions" data-role="actions"></div>
        <button type="button" class="bulk-bar__close" data-role="close" aria-label="${escapeHTML(bulkText("bulk.clear"))}" title="${escapeHTML(bulkText("bulk.clear"))}">
          ${iconSvg("x")}
        </button>
      `;

      const actionsHost = el.querySelector('[data-role="actions"]');
      const danger = [];
      const safe = [];
      this.actions.forEach(a => (a.variant === "danger" ? danger : safe).push(a));

      const renderBtn = (a) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "bulk-bar__btn" + (a.variant === "danger" ? " bulk-bar__btn--danger" : "");
        btn.dataset.action = a.id;
        const iconHtml = a.icon ? iconSvg(a.icon, "bulk-bar__btn-icon") : "";
        const labelHtml = `<span data-role="label">${escapeHTML(a.label)}</span>`;
        btn.innerHTML = iconHtml + labelHtml;
        btn.addEventListener("click", () => this._handleClick(a));
        return btn;
      };

      safe.forEach(a => actionsHost.appendChild(renderBtn(a)));
      if (safe.length && danger.length) {
        const div = document.createElement("span");
        div.className = "bulk-bar__divider";
        actionsHost.appendChild(div);
      }
      danger.forEach(a => actionsHost.appendChild(renderBtn(a)));

      el.querySelector('[data-role="close"]').addEventListener("click", () => {
        if (this.busy) return;
        this.table.clearSelection();
      });

      this.container.appendChild(el);
      this.el = el;
    }

    update(sel) {
      const total = sel.total || 0;
      if (total === 0) {
        this._hide();
        this._prevCount = 0;
        return;
      }
      const countEl = this.el.querySelector('[data-role="count"]');
      const label = this.countLabel ? this.countLabel(total) : bulkText("bulk.count", { n: total });
      countEl.textContent = label;
      if (total !== this._prevCount) {
        countEl.classList.remove("is-pulse");
        // restart animation
        void countEl.offsetWidth;
        countEl.classList.add("is-pulse");
      }
      this._prevCount = total;
      this._show();
    }

    _show() {
      this.el.classList.add("is-visible");
      document.body.classList.add("has-bulk-bar");
    }

    _hide() {
      this.el.classList.remove("is-visible");
      // aria-hidden is managed exclusively by _setAriaHiddenWhileModal —
      // do not overwrite it here, otherwise we may lift pointer-events
      // off the bar while a confirm modal is still open above it.
      document.body.classList.remove("has-bulk-bar");
      this._resetSoftArmed();
    }

    _resetSoftArmed() {
      if (!this.softArmed) return;
      clearTimeout(this.softArmed.timer);
      const btn = this.el.querySelector(`[data-action="${CSS.escape(this.softArmed.actionId)}"]`);
      const action = this.actions.find(a => a.id === this.softArmed.actionId);
      if (btn && action) {
        btn.classList.remove("bulk-bar__btn--soft-armed");
        const labelEl = btn.querySelector('[data-role="label"]');
        if (labelEl) labelEl.textContent = action.label;
      }
      this.softArmed = null;
    }

    _handleClick(action) {
      if (this.busy) return;
      const sel = this.table.getSelection();
      if (!sel || !sel.total) return;

      const mode = action.confirm || "none";
      if (mode === "soft") {
        if (this.softArmed && this.softArmed.actionId === action.id) {
          this._resetSoftArmed();
          this._runAction(action, sel);
          return;
        }
        this._armSoft(action);
        return;
      }
      if (mode === "modal") {
        this._modalConfirm(action, sel);
        return;
      }
      if (mode === "type-to-confirm") {
        this._typeConfirm(action, sel);
        return;
      }
      // default — no confirm
      this._runAction(action, sel);
    }

    _armSoft(action) {
      this._resetSoftArmed();
      const btn = this.el.querySelector(`[data-action="${CSS.escape(action.id)}"]`);
      if (!btn) return;
      btn.classList.add("bulk-bar__btn--soft-armed");
      const labelEl = btn.querySelector('[data-role="label"]');
      if (labelEl) labelEl.textContent = bulkText("bulk.confirm.softPrompt") + " · " + action.label;
      this.softArmed = {
        actionId: action.id,
        timer: setTimeout(() => this._resetSoftArmed(), SOFT_CONFIRM_TIMEOUT)
      };
    }

    _modalConfirm(action, sel) {
      const title = action.confirmTitle || bulkText("bulk.confirm.modalTitle");
      // text is plain string — showConfirmModal uses textContent (see modal.js),
      // so HTML in confirmText would be displayed literally, not interpreted.
      const text = (action.confirmText && action.confirmText(sel)) ||
        `${action.label}: ${fmtNum(sel.total)}.`;
      global.showConfirmModal({
        title: title,
        text: text,
        confirmText: bulkText("bulk.confirm.modalConfirm"),
        cancelText: bulkText("bulk.confirm.modalCancel"),
        isDanger: action.variant === "danger",
        onConfirm: () => this._runAction(action, sel)
      });
      this._setAriaHiddenWhileModal();
    }

    _setAriaHiddenWhileModal() {
      // While the confirm modal is open the bar must not catch clicks.
      this.el.setAttribute("aria-hidden", "true");
      const overlay = document.getElementById("globalModalOverlay");
      if (!overlay) return;
      const observer = new MutationObserver(() => {
        if (!overlay.classList.contains("modal-overlay--active")) {
          this.el.setAttribute("aria-hidden", "false");
          observer.disconnect();
        }
      });
      observer.observe(overlay, { attributes: true, attributeFilter: ["class"] });
    }

    _typeConfirm(action, sel) {
      const expected = (action.typeWord || bulkText("bulk.confirm.type.word")).toLowerCase();
      const total = sel.total;
      const html = `
        <div class="modal-overlay modal-overlay--active" id="bulkTypeConfirmOverlay" role="dialog" aria-modal="true">
          <div class="modal">
            <div class="modal__header">
              ${iconSvg("alert-triangle", "lucide--lg")}
              <span style="margin-left:8px;">${escapeHTML(action.confirmTitle || bulkText("bulk.confirm.type.title"))}</span>
            </div>
            <div class="modal__body">
              <p style="color:var(--color-text-muted); font-size:13px; white-space:pre-line;">${escapeHTML(action.confirmText ? action.confirmText(sel) : `Будет удалено ${fmtNum(total)}. Действие необратимо.`)}</p>
              <p class="bulk-confirm__hint">${escapeHTML(bulkText("bulk.confirm.type.hint"))} <span class="bulk-confirm__expected">${escapeHTML(expected)}</span></p>
              <input type="text" id="bulkTypeConfirmInput" class="form-input bulk-confirm__input" autocomplete="off" placeholder="${escapeHTML(expected)}">
            </div>
            <div class="modal__footer">
              <button id="bulkTypeConfirmCancel" type="button" class="btn btn--ghost">${escapeHTML(bulkText("bulk.confirm.modalCancel"))}</button>
              <button id="bulkTypeConfirmOk" type="button" class="btn btn--danger" disabled>${escapeHTML(bulkText("bulk.confirm.type.button", { n: total }))}</button>
            </div>
          </div>
        </div>
      `;
      const host = document.createElement("div");
      host.innerHTML = html;
      const overlay = host.firstElementChild;
      document.body.appendChild(overlay);

      const input = overlay.querySelector("#bulkTypeConfirmInput");
      const okBtn = overlay.querySelector("#bulkTypeConfirmOk");
      const cancelBtn = overlay.querySelector("#bulkTypeConfirmCancel");

      const close = () => {
        overlay.remove();
        this.el.setAttribute("aria-hidden", "false");
        document.removeEventListener("keydown", onKey);
      };
      const onKey = (e) => {
        if (e.key === "Escape") { e.preventDefault(); close(); }
        else if (e.key === "Enter" && !okBtn.disabled) { e.preventDefault(); confirm(); }
      };
      const confirm = () => { close(); this._runAction(action, sel); };

      input.addEventListener("input", () => {
        const v = input.value.trim().toLowerCase();
        okBtn.disabled = v !== expected;
      });
      okBtn.addEventListener("click", confirm);
      cancelBtn.addEventListener("click", close);
      overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
      document.addEventListener("keydown", onKey);

      this.el.setAttribute("aria-hidden", "true");
      setTimeout(() => input.focus(), FOCUS_DELAY_MS);
    }

    async _runAction(action, sel) {
      const btn = this.el.querySelector(`[data-action="${CSS.escape(action.id)}"]`);
      const originalLabel = action.label;
      this.busy = true;
      this._setAllButtonsDisabled(true);
      if (btn) {
        const labelEl = btn.querySelector('[data-role="label"]');
        if (labelEl) labelEl.textContent = bulkText("bulk.actionInProgress");
        // swap icon to spinner
        const iconEl = btn.querySelector(".lucide");
        if (iconEl) {
          const placeholder = document.createElement("span");
          placeholder.className = "bulk-bar__btn-spinner";
          placeholder.dataset.role = "spinner";
          iconEl.replaceWith(placeholder);
        }
      }
      try {
        const payload = this._buildPayload(sel);
        const result = await action.handler(payload, sel);
        if (result && result.cancelled) return;  // handler-side cancellation (custom picker modal)
        this._afterAction(action, sel, result);
      } catch (err) {
        console.error("bulk action failed", err);
        document.body.dispatchEvent(new CustomEvent("showToast", {
          detail: { message: bulkText("bulk.actionFailed"), type: "error" }
        }));
      } finally {
        this.busy = false;
        this._setAllButtonsDisabled(false);
        if (btn) {
          const labelEl = btn.querySelector('[data-role="label"]');
          if (labelEl) labelEl.textContent = originalLabel;
          const spinner = btn.querySelector('[data-role="spinner"]');
          if (spinner && action.icon) {
            const wrap = document.createElement("span");
            wrap.innerHTML = iconSvg(action.icon, "bulk-bar__btn-icon");
            spinner.replaceWith(wrap.firstElementChild);
          } else if (spinner) {
            spinner.remove();
          }
        }
      }
    }

    _setAllButtonsDisabled(disabled) {
      this.el.querySelectorAll(".bulk-bar__btn, .bulk-bar__close").forEach(b => {
        b.disabled = disabled;
      });
    }

    _buildPayload(sel) {
      // Compose BulkTarget envelope expected by the backend.
      if (sel.mode === "ids") {
        return { target: { kind: "ids", ids: sel.ids } };
      }
      if (sel.mode === "all_by_filter") {
        return { target: { kind: "filter", filter: sel.filter || {} } };
      }
      return null;
    }

    _afterAction(action, sel, result) {
      const total = result && typeof result.total === "number" ? result.total : sel.total;
      const ok = result && typeof result.ok === "number" ? result.ok : total;
      const failed = (result && Array.isArray(result.failed)) ? result.failed : [];

      if (failed.length === 0) {
        document.body.dispatchEvent(new CustomEvent("showToast", {
          detail: {
            message: bulkText("bulk.actionDone", { n: ok }),
            type: "success"
          }
        }));
      } else {
        this._showPartialToast(ok, total, failed);
      }

      // Reload table + clear selection, then flash failed rows.
      const failedIds = failed.map(f => String(f.id));
      const tbl = this.table;
      tbl.clearSelection();
      Promise.resolve(tbl.load && tbl.load()).then(() => {
        if (failedIds.length) tbl.markFailedRows(failedIds);
      });
    }

    _showPartialToast(ok, total, failed) {
      const container = document.getElementById("toast-container");
      if (!container) return;
      const el = document.createElement("div");
      el.className = "toast toast--warning";
      el.innerHTML = `
        ${iconSvg("alert-triangle", "toast__icon")}
        <div class="toast__body">
          <div class="toast__title">${escapeHTML(bulkText("bulk.actionPartial.title", { ok: ok, total: total }))}</div>
          <div class="toast__sub">${escapeHTML(bulkText("bulk.actionPartial.sub", { failed: failed.length }))}</div>
          <button type="button" class="toast__action" data-role="details">${escapeHTML(bulkText("bulk.actionPartial.details"))}</button>
        </div>
      `;
      el.querySelector('[data-role="details"]').addEventListener("click", () => this._openFailuresModal(failed));
      container.appendChild(el);
      setTimeout(() => el.remove(), 12000);
    }

    _openFailuresModal(failed) {
      const enriched = this.table.buildFailureRows
        ? this.table.buildFailureRows(failed)
        : failed.map(f => ({ id: f.id, reason: f.reason, name: null }));

      const rowsHTML = enriched.map(f => `
        <tr>
          <td>${escapeHTML(f.name || "—")}</td>
          <td class="bulk-failures-id">${escapeHTML(f.id)}</td>
          <td class="bulk-failures-reason">${escapeHTML(bulkReason(f.reason))}</td>
        </tr>
      `).join("");

      const html = `
        <div class="modal-overlay modal-overlay--active" id="bulkFailuresOverlay" role="dialog" aria-modal="true">
          <div class="modal modal--lg">
            <div class="modal__header">
              ${iconSvg("alert-triangle", "lucide--lg")}
              <span style="margin-left:8px;">${escapeHTML(bulkText("bulk.failures.title"))}</span>
            </div>
            <div class="modal__body" style="max-height:60vh; overflow-y:auto;">
              <table class="bulk-failures-table">
                <thead>
                  <tr>
                    <th>${escapeHTML(bulkText("bulk.failures.col.name"))}</th>
                    <th>${escapeHTML(bulkText("bulk.failures.col.id"))}</th>
                    <th>${escapeHTML(bulkText("bulk.failures.col.reason"))}</th>
                  </tr>
                </thead>
                <tbody>${rowsHTML}</tbody>
              </table>
            </div>
            <div class="modal__footer">
              <button id="bulkFailuresClose" type="button" class="btn btn--primary">${escapeHTML(bulkText("bulk.failures.close"))}</button>
            </div>
          </div>
        </div>
      `;
      const host = document.createElement("div");
      host.innerHTML = html;
      const overlay = host.firstElementChild;
      document.body.appendChild(overlay);

      const onKey = (e) => { if (e.key === "Escape") close(); };
      const close = () => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
      };
      overlay.querySelector("#bulkFailuresClose").addEventListener("click", close);
      overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
      document.addEventListener("keydown", onKey);
    }
  }

  global.BulkActionBar = BulkActionBar;
})(window);
