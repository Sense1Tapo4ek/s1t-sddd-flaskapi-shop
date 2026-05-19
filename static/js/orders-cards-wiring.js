/* Orders CardsFeed wiring.
   One-tap status pills per card. No drawer, no bulk actions.
*/

(function (global) {
  "use strict";

  function esc(s) {
    if (typeof global.esc === "function") return global.esc(s);
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

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

  function renderOrderActions(o) {
    return ORDER_STATUS_OPTIONS.map(function (opt) {
      var isCurrent = opt.value === o.status;
      var cls = "cf-status-pill" + (isCurrent ? " cf-status-pill--current" : "");
      var disabled = isCurrent ? " disabled" : "";
      return '<button type="button" class="' + cls + '" data-action="set-status" data-status="' +
             esc(opt.value) + '"' + disabled + '>' + esc(opt.label) + '</button>';
    }).join("");
  }

  function showToast(message, type) {
    document.body.dispatchEvent(new CustomEvent("showToast", {
      detail: { message: message, type: type || "info" }
    }));
  }

  function initOrdersFeed(canManage) {
    var feed = new global.CardsFeed({
      instanceName:    "ordersFeed",
      endpoint:        "/admin/orders/search",
      schemaEndpoint:  "/admin/orders/search/schema",
      containerId:     "orders-feed",
      defaultSortBy:   "created_at",
      defaultSortDir:  "desc",
      rowIdKey:        "id",
      getRowName:      function (o) { return "Заказ #" + o.id; },
      renderCard:      renderOrderCard,
      renderCardActions: canManage ? renderOrderActions : null,
      onActionClick:   canManage ? function (item, action, target) {
        if (action !== "set-status") return;
        var newStatus = target.getAttribute("data-status");
        if (!newStatus || newStatus === item.status) return;
        global.api.patch("/admin/orders/" + item.id + "/status", { status: newStatus })
          .then(function (res) {
            if (res && res._failed) return;
            showToast("Статус заказа #" + item.id + " → " + (ORDER_STATUS_LABELS[newStatus] || newStatus), "success");
            feed.load();
          });
      } : null,
      selectable:      false,
      showDrawerBtn:   false,
      initialFilters:  { "status__neq": "archived" },
      onLoad: function (data) {
        var el = document.getElementById("orders-tab-count");
        if (el) el.textContent = data.total > 0 ? "(" + data.total + ")" : "";
      },
    });

    feed._statusOptionsList = ORDER_STATUS_OPTIONS;
    feed.load();
    global.ordersFeed = feed;
  }

  global.initOrdersFeed = initOrdersFeed;
})(window);
