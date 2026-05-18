/* Orders CardsFeed wiring.
   Bootstraps a CardsFeed instance for /admin/orders/search.
   Replaces bulk-orders-wiring.js (which was SmartTable-specific).
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

  var ORDER_STATUS_LABELS = {
    new:       "Новый",
    confirmed: "Подтверждён",
    completed: "Выполнен",
    canceled:  "Отменён",
    archived:  "Архив",
  };

  var ORDER_STATUS_BADGE = {
    new:       "badge--new",
    confirmed: "",
    completed: "badge--done",
    canceled:  "badge--trash",
    archived:  "badge--archived",
  };

  var ORDER_STATUS_OPTIONS = [
    { value: "new",       label: "Новый" },
    { value: "confirmed", label: "Подтверждён" },
    { value: "completed", label: "Выполнен" },
    { value: "canceled",  label: "Отменён" },
    { value: "archived",  label: "Архив" },
  ];

  function statusBadge(status) {
    var label = ORDER_STATUS_LABELS[status] || status;
    var cls   = ORDER_STATUS_BADGE[status] || "";
    return '<span class="badge ' + esc(cls) + '">' + esc(label) + '</span>';
  }

  // ─── Card renderer ────────────────────────────────────────────────────────

  function renderOrderCard(o) {
    var itemsCount = Array.isArray(o.items) ? o.items.length : 0;
    var total = o.total != null ? String(o.total) : "—";
    var delivery = o.delivery_method || "—";
    var comment = o.comment ? String(o.comment).slice(0, 120) : "";
    var commentHtml = comment
      ? '<div class="cf-card__comment">«' + esc(comment) + (o.comment && o.comment.length > 120 ? "…" : "") + '»</div>'
      : "";

    return (
      '<div class="cf-card-body">' +
        '<div class="cf-card-body__head">' +
          statusBadge(o.status) +
          '<span class="cf-card-body__meta">#' + esc(o.id) + ' · ' + esc(o.created_at) + ' · customer=' + esc(o.customer_user_id) + '</span>' +
        '</div>' +
        '<div class="cf-card-body__content">' +
          '<div>' + esc(itemsCount) + ' товаров · ' + esc(total) + ' Br · ' + esc(delivery) + '</div>' +
          commentHtml +
        '</div>' +
      '</div>'
    );
  }

  // ─── Bulk bar wiring ──────────────────────────────────────────────────────

  function statusControls() {
    var state = { status: null };
    var optionsHtml = [
      { value: "new",       i18n: "bulk.orders.status.new" },
      { value: "confirmed", i18n: "bulk.orders.status.confirmed" },
      { value: "completed", i18n: "bulk.orders.status.completed" },
      { value: "canceled",  i18n: "bulk.orders.status.canceled" },
    ].map(function (opt) {
      return '<label style="display:block; padding:6px 4px;"><input type="radio" name="bulkOrderStatus" value="' + esc(opt.value) + '"> ' + esc(bulkT(opt.i18n) || opt.value) + '</label>';
    }).join("");
    var html = '<fieldset><legend>' + esc(bulkT("bulk.orders.modal.statusLegend") || "Новый статус") + '</legend>' + optionsHtml + '</fieldset>';
    return {
      html: html,
      onMount: function (overlay, ctx) {
        ctx.setValid(false);
        overlay.addEventListener("change", function (e) {
          if (e.target && e.target.name === "bulkOrderStatus") {
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

  function mountOrdersBulkBar(feed) {
    if (!feed) return null;
    if (!global.BulkActionBar) return null;
    return new global.BulkActionBar({
      table: feed,
      getRowName: function (o) { return "Заказ #" + o.id; },
      actions: [
        {
          id: "status",
          label: bulkT("bulk.orders.action.status") || "Изменить статус",
          icon: "arrow-right-circle",
          confirm: "modal",
          explain: function () { return bulkT("bulk.orders.explain.status") || "Выбранным заказам будет назначен новый статус."; },
          customControls: function () { return statusControls(); },
          handler: function (payload) { return postBulk("/admin/orders/bulk/status", payload); },
        },
      ],
    });
  }

  // ─── Init ────────────────────────────────────────────────────────────────

  function initOrdersFeed(canManage) {
    var feed = new global.CardsFeed({
      instanceName:   "ordersFeed",
      endpoint:       "/admin/orders/search",
      schemaEndpoint: "/admin/orders/search/schema",
      containerId:    "orders-feed",
      defaultSortBy:  "created_at",
      defaultSortDir: "desc",
      rowIdKey:       "id",
      getRowName:     function (o) { return "Заказ #" + o.id; },
      renderCard:     renderOrderCard,
      selectable:     !!canManage,
      initialFilters: { "status__neq": "archived" },
      onLoad: function (data) {
        var el = document.getElementById("orders-tab-count");
        if (el) el.textContent = data.total > 0 ? "(" + data.total + ")" : "";
      },
    });

    feed._statusOptionsList = ORDER_STATUS_OPTIONS;

    feed.load();

    if (canManage) {
      // Mount bulk bar after first load so feed is ready
      setTimeout(function () { mountOrdersBulkBar(feed); }, 0);
    }

    global.ordersFeed = feed;
  }

  global.initOrdersFeed    = initOrdersFeed;
  global.mountOrdersBulkBar = mountOrdersBulkBar;
})(window);
