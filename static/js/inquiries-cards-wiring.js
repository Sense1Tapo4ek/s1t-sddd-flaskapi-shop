/* Inquiries CardsFeed wiring.
   Bootstraps a CardsFeed instance for /admin/inquiries/search.
   Replaces bulk-inquiries-wiring.js (which was SmartTable-specific).
*/

(function (global) {
  "use strict";

  function esc(s) {
    if (typeof global.esc === "function") return global.esc(s);
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function bulkT(key, params) {
    return (typeof global.bulkT === "function") ? global.bulkT(key, params) : key;
  }

  // ─── Status labels / classes ──────────────────────────────────────────────

  var INQUIRY_STATUS_LABELS = {
    new:         "Новое",
    in_progress: "В обработке",
    closed:      "Закрыто",
    archived:    "Архив",
  };

  var INQUIRY_STATUS_BADGE = {
    new:         "badge--new",
    in_progress: "",
    closed:      "badge--done",
    archived:    "badge--archived",
  };

  var INQUIRY_STATUS_OPTIONS = [
    { value: "new",         label: "Новое" },
    { value: "in_progress", label: "В обработке" },
    { value: "closed",      label: "Закрыто" },
    { value: "archived",    label: "Архив" },
  ];

  function statusBadge(status) {
    var label = INQUIRY_STATUS_LABELS[status] || status;
    var cls   = INQUIRY_STATUS_BADGE[status] || "";
    return '<span class="badge ' + esc(cls) + '">' + esc(label) + '</span>';
  }

  // ─── Card renderer ────────────────────────────────────────────────────────

  function renderInquiryCard(i) {
    var contact = i.phone || i.contact_email || "—";
    var message = i.message ? String(i.message).slice(0, 160) : "";
    var messageHtml = message
      ? '<div class="cf-card__comment">«' + esc(message) + (i.message && i.message.length > 160 ? "…" : "") + '»</div>'
      : "";

    return (
      '<div class="cf-card-body">' +
        '<div class="cf-card-body__head">' +
          statusBadge(i.status) +
          '<span class="cf-card-body__meta">#' + esc(i.id) + ' · ' + esc(i.created_at) + '</span>' +
        '</div>' +
        '<div class="cf-card-body__content">' +
          '<div>' + esc(i.name) + ' · ' + esc(contact) + '</div>' +
          messageHtml +
        '</div>' +
      '</div>'
    );
  }

  // ─── Bulk bar wiring ──────────────────────────────────────────────────────

  function statusControls() {
    var state = { status: null };
    var optionsHtml = [
      { value: "new",         i18n: "bulk.inquiries.status.new" },
      { value: "in_progress", i18n: "bulk.inquiries.status.in_progress" },
      { value: "closed",      i18n: "bulk.inquiries.status.closed" },
      { value: "archived",    i18n: "bulk.inquiries.status.archived" },
    ].map(function (opt) {
      return '<label style="display:block; padding:6px 4px;"><input type="radio" name="bulkInquiryStatus" value="' + esc(opt.value) + '"> ' + esc(bulkT(opt.i18n) || opt.value) + '</label>';
    }).join("");
    var html = '<fieldset><legend>' + esc(bulkT("bulk.inquiries.modal.statusLegend") || "Новый статус") + '</legend>' + optionsHtml + '</fieldset>';
    return {
      html: html,
      onMount: function (overlay, ctx) {
        ctx.setValid(false);
        overlay.addEventListener("change", function (e) {
          if (e.target && e.target.name === "bulkInquiryStatus") {
            state.status = e.target.value;
            ctx.setValid(true);
          }
        });
      },
      validate: function () { return state.status != null; },
      getValue: function () { return { status: state.status }; },
    };
  }

  async function postBulk(url, body) {
    var res = await global.api.post(url, body);
    if (res && res._failed) return { cancelled: true };
    return res;
  }

  function mountInquiriesBulkBar(feed) {
    if (!feed) return null;
    if (!global.BulkActionBar) return null;
    return new global.BulkActionBar({
      table: feed,
      getRowName: function (i) { return "Обращение #" + i.id; },
      actions: [
        {
          id: "status",
          label: bulkT("bulk.inquiries.action.status") || "Изменить статус",
          icon: "arrow-right-circle",
          confirm: "modal",
          explain: function () { return bulkT("bulk.inquiries.explain.status") || "Выбранным обращениям будет назначен новый статус."; },
          customControls: function () { return statusControls(); },
          handler: function (payload) { return postBulk("/admin/inquiries/bulk/status", payload); },
        },
        {
          id: "archive",
          label: bulkT("bulk.inquiries.action.archive") || "Архивировать",
          icon: "archive",
          confirm: "toast",
          explain: function () { return bulkT("bulk.inquiries.explain.archive") || "Выбранные обращения будут перемещены в архив."; },
          handler: function (payload) { return postBulk("/admin/inquiries/bulk/archive", payload); },
        },
      ],
    });
  }

  // ─── Init ────────────────────────────────────────────────────────────────

  function initInquiriesFeed(canManage) {
    var feed = new global.CardsFeed({
      instanceName:   "inquiriesFeed",
      endpoint:       "/admin/inquiries/search",
      schemaEndpoint: "/admin/inquiries/search/schema",
      containerId:    "inquiries-feed",
      defaultSortBy:  "created_at",
      defaultSortDir: "desc",
      rowIdKey:       "id",
      getRowName:     function (i) { return "Обращение #" + i.id; },
      renderCard:     renderInquiryCard,
      selectable:     !!canManage,
      initialFilters: { "status__neq": "archived" },
      onLoad: function (data) {
        var el = document.getElementById("inquiries-tab-count");
        if (el) el.textContent = data.total > 0 ? "(" + data.total + ")" : "";
      },
    });

    feed._statusOptionsList = INQUIRY_STATUS_OPTIONS;

    feed.load();

    if (canManage) {
      setTimeout(function () { mountInquiriesBulkBar(feed); }, 0);
    }

    global.inquiriesFeed = feed;
  }

  global.initInquiriesFeed    = initInquiriesFeed;
  global.mountInquiriesBulkBar = mountInquiriesBulkBar;
})(window);
