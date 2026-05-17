/* Bulk Action Bar — floating capsule that surfaces actions on the
   current SmartTable selection.
   Spec: docs/superpowers/specs/2026-05-15-bulk-actions-design.md §4.2, §10.

   Confirmation model (post-2026-05-17 redesign):
     every action opens a single unified modal — header (icon + label),
     explain block, optional custom controls (category picker, tag
     picker, status picker), collapsible selection preview, footer with
     [Cancel] + primary button. Primary is red when variant === "danger".
     No soft-arm, no type-to-confirm — all actions share one shape.
*/

(function (global) {
  "use strict";

  const FOCUS_DELAY_MS = 30;       // one paint cycle before focusing a freshly mounted modal input

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
      // `inert` on the bar (set while a modal is open) is preserved here
      // intentionally — _openActionModal owns its lifecycle.
      document.body.classList.remove("has-bulk-bar");
    }

    _handleClick(action) {
      if (this.busy) return;
      const sel = this.table.getSelection();
      if (!sel || !sel.total) return;
      this._openActionModal(action, sel);
    }

    // ─── Unified action modal ─────────────────────────────────────────
    //
    // Every bulk action — destructive or not — goes through this single
    // shape. Per-action customisation lives in three optional callbacks
    // on the action descriptor:
    //
    //   explain(sel)        : string  — "what will happen" plain text
    //   customControls(sel) : { html, onMount(modalEl, ctx)?, getValue() } | null
    //   primaryLabel(sel)   : string  — overrides default "<label> N"
    //
    // The handler is invoked with payload merged with whatever
    // customControls.getValue() returned, so wiring stays declarative.

    _openActionModal(action, sel) {
      const explainText = (typeof action.explain === "function")
        ? action.explain(sel)
        : (action.explain || "");
      const controls = (typeof action.customControls === "function")
        ? action.customControls(sel)
        : null;
      const isDanger = action.variant === "danger";
      const primaryClass = isDanger ? "btn btn--danger" : "btn btn--primary";
      const primaryLabel = (typeof action.primaryLabel === "function")
        ? action.primaryLabel(sel)
        : bulkText("bulk.modal.primary", { label: action.label, n: sel.total });
      const cancelLabel = bulkText("bulk.modal.cancel");

      const scopeText = sel.mode === "all_by_filter"
        ? bulkText("bulk.scope.filter", { n: sel.total })
        : bulkText("bulk.scope.ids", { n: sel.total });
      const html = `
        <div class="modal-overlay modal-overlay--active" id="bulkActionOverlay" role="dialog" aria-modal="true">
          <div class="modal">
            <div class="modal__header">
              ${iconSvg(action.icon || "info", "lucide--lg")}
              <span style="margin-left:8px;">${escapeHTML(action.label)}</span>
              <button class="modal__close" type="button" data-role="close" aria-label="${escapeHTML(cancelLabel)}">&times;</button>
            </div>
            <div class="modal__body">
              ${explainText ? `<div class="bulk-modal__explain">${escapeHTML(explainText)}</div>` : ""}
              ${controls && controls.html ? `<div class="bulk-modal__custom" data-role="custom">${controls.html}</div>` : ""}
              <p class="bulk-modal__scope">${escapeHTML(scopeText)}</p>
            </div>
            <div class="modal__footer">
              <button type="button" class="btn btn--ghost" data-role="cancel">${escapeHTML(cancelLabel)}</button>
              <button type="button" class="${primaryClass}" data-role="confirm">${escapeHTML(primaryLabel)}</button>
            </div>
          </div>
        </div>
      `;
      const host = document.createElement("div");
      host.innerHTML = html;
      const overlay = host.firstElementChild;
      document.body.appendChild(overlay);

      const confirmBtn = overlay.querySelector('[data-role="confirm"]');

      // Mount custom controls and wire validity → primary-button state.
      // setValid accepts boolean (toggles disabled) OR object
      // { valid?: bool, danger?: bool } — the danger flag lets a control
      // promote the primary button to btn--danger at runtime (e.g., the
      // tag picker switching to "replace" mode).
      let getValue = () => ({});
      const setValid = (state) => {
        if (typeof state === "boolean") {
          confirmBtn.disabled = !state;
          return;
        }
        if (state && typeof state === "object") {
          if (typeof state.valid === "boolean") confirmBtn.disabled = !state.valid;
          if ("danger" in state) {
            confirmBtn.classList.toggle("btn--danger", !!state.danger);
            confirmBtn.classList.toggle("btn--primary", !state.danger);
          }
        }
      };
      if (controls) {
        if (typeof controls.getValue === "function") getValue = () => controls.getValue();
        if (typeof controls.onMount === "function") {
          controls.onMount(overlay, { setValid: setValid });
        }
        // If validate() exists, disable until valid; otherwise enabled.
        if (typeof controls.validate === "function") {
          confirmBtn.disabled = !controls.validate();
        }
      }

      const close = () => {
        overlay.remove();
        this.el.inert = false;
        document.removeEventListener("keydown", onKey);
      };
      const onKey = (e) => {
        if (e.key === "Escape") { e.preventDefault(); close(); return; }
        if (e.key !== "Enter" || confirmBtn.disabled) return;
        // Don't submit while user is typing inside custom controls
        // (category search, tag-picker editable input, etc.).
        const tag = e.target && e.target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        e.preventDefault();
        submit();
      };
      const submit = () => {
        if (confirmBtn.disabled) return;
        const extra = getValue() || {};
        close();
        this._runAction(action, sel, extra);
      };

      overlay.querySelector('[data-role="cancel"]').addEventListener("click", close);
      overlay.querySelector('[data-role="close"]').addEventListener("click", close);
      overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
      confirmBtn.addEventListener("click", submit);
      document.addEventListener("keydown", onKey);

      this.el.inert = true;
      // Focus first interactive element inside the custom slot when present,
      // otherwise the confirm button.
      setTimeout(() => {
        const firstInput = overlay.querySelector('[data-role="custom"] input, [data-role="custom"] button, [data-role="custom"] select');
        if (firstInput) firstInput.focus();
        else confirmBtn.focus();
      }, FOCUS_DELAY_MS);
    }

    async _runAction(action, sel, extra) {
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
        const payload = { ...this._buildPayload(sel), ...(extra || {}) };
        const result = await action.handler(payload, sel);
        // api.js already surfaces a toast on backend failure; postBulk
        // wraps that into {cancelled:true}, but tolerate raw _failed too.
        if (result && (result.cancelled || result._failed)) return;
        this._afterAction(action, sel, result);
      } catch (err) {
        console.error("[bulk] action failed:", action.id, "err=", err, "sel=", sel);
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
