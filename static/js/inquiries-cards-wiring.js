/* Inquiries CardsFeed wiring.
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

  function renderInquiryActions(i) {
    return INQUIRY_STATUS_OPTIONS.map(function (opt) {
      var isCurrent = opt.value === i.status;
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

  function initInquiriesFeed(canManage) {
    var feed = new global.CardsFeed({
      instanceName:    "inquiriesFeed",
      endpoint:        "/admin/inquiries/search",
      schemaEndpoint:  "/admin/inquiries/search/schema",
      containerId:     "inquiries-feed",
      defaultSortBy:   "created_at",
      defaultSortDir:  "desc",
      rowIdKey:        "id",
      getRowName:      function (i) { return "Обращение #" + i.id; },
      renderCard:      renderInquiryCard,
      renderCardActions: canManage ? renderInquiryActions : null,
      onActionClick:   canManage ? function (item, action, target) {
        if (action !== "set-status") return;
        var newStatus = target.getAttribute("data-status");
        if (!newStatus || newStatus === item.status) return;
        global.api.patch("/admin/inquiries/" + item.id + "/status", { status: newStatus })
          .then(function (res) {
            if (res && res._failed) return;
            showToast("Статус обращения #" + item.id + " → " + (INQUIRY_STATUS_LABELS[newStatus] || newStatus), "success");
            feed.load();
          });
      } : null,
      selectable:      false,
      showDrawerBtn:   false,
      initialFilters:  { "status__neq": "archived" },
      onLoad: function (data) {
        var el = document.getElementById("inquiries-tab-count");
        if (el) el.textContent = data.total > 0 ? "(" + data.total + ")" : "";
      },
    });

    feed._statusOptionsList = INQUIRY_STATUS_OPTIONS;
    feed.load();
    global.inquiriesFeed = feed;
  }

  global.initInquiriesFeed = initInquiriesFeed;
})(window);
