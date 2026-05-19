/* CardsFeed — generic card-based feed component.
   SmartTable-compatible interface: load(), lastData, rowIdKey,
   getSelected(), onSelectionChange, currentFilters, getRowName.
   Spec: docs/superpowers/plans/2026-05-17-inquiries-and-orders-redesign.md §Stage 8.
*/

(function (global) {
  "use strict";

  // ─── Helpers ──────────────────────────────────────────────────────────────

  function esc(s) {
    if (typeof global.esc === "function") return global.esc(s);
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function debounce(fn, ms) {
    var timer;
    return function () {
      clearTimeout(timer);
      var args = arguments;
      var ctx = this;
      timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  // ─── CardsFeed ───────────────────────────────────────────────────────────

  function CardsFeed(opts) {
    this.instanceName     = opts.instanceName;
    this.endpoint         = opts.endpoint;
    this.schemaEndpoint   = opts.schemaEndpoint || null;
    this.containerId      = opts.containerId;
    this.defaultSortBy    = opts.defaultSortBy || "created_at";
    this.defaultSortDir   = opts.defaultSortDir || "desc";
    this.rowIdKey         = opts.rowIdKey || "id";
    this.getRowName       = typeof opts.getRowName === "function" ? opts.getRowName : function (item) { return String(item[this.rowIdKey]); }.bind(this);
    this.renderCard       = typeof opts.renderCard === "function" ? opts.renderCard : function () { return ""; };
    this.selectable       = !!opts.selectable;
    this.showDrawerBtn    = opts.showDrawerBtn !== false;  // default true — backward compat
    this.renderCardActions = typeof opts.renderCardActions === "function" ? opts.renderCardActions : null;
    this.onActionClick    = typeof opts.onActionClick === "function" ? opts.onActionClick : null;
    this._statusOptionsList = Array.isArray(opts.statusOptions) ? opts.statusOptions : null;
    this.initialFilters   = opts.initialFilters || {};
    this._onLoadCb        = typeof opts.onLoad === "function" ? opts.onLoad : null;
    this._selChangeCbs    = [];

    // State
    this._page       = 1;
    this._limit      = 20;
    this._sortBy     = this.defaultSortBy;
    this._sortDir    = this.defaultSortDir;
    this._filters    = Object.assign({}, this.initialFilters);
    this._query      = "";
    this._showAll    = false;  // when true, don't apply initial "hide archived" filter
    this._selected   = {};    // id -> item
    this._data       = { items: [], total: 0, page: 1, limit: 20 };
    this._loading    = false;

    this._container  = null;
    this._drawer     = null;

    this._build();

    // Register globally
    if (!global.cardsFeeds) global.cardsFeeds = {};
    global.cardsFeeds[this.instanceName] = this;
  }

  // ─── SmartTable-compatible interface ─────────────────────────────────────

  Object.defineProperty(CardsFeed.prototype, "lastData", {
    get: function () { return this._data; }
  });

  Object.defineProperty(CardsFeed.prototype, "currentFilters", {
    get: function () {
      var f = Object.assign({}, this._filters);
      if (this._query) f.q = this._query;
      return f;
    }
  });

  CardsFeed.prototype.getSelected = function () {
    return new Set(Object.keys(this._selected).map(Number));
  };

  CardsFeed.prototype.getSelection = function () {
    var ids = Object.keys(this._selected).map(Number);
    if (ids.length === 0) return { total: 0, mode: "ids", ids: [] };
    return { total: ids.length, mode: "ids", ids: ids, filter: this.currentFilters };
  };

  CardsFeed.prototype.clearSelection = function () {
    this._selected = {};
    this._renderCards();
    this._fireSelChange();
  };

  // BulkActionBar treats `table.onSelectionChange` as both a method
  // (table.onSelectionChange(cb)) and a property setter
  // (table.onSelectionChange = cb). Use a property with get/set so the
  // setter form works; the getter returns the latest callback.
  Object.defineProperty(CardsFeed.prototype, "onSelectionChange", {
    get: function () {
      // return the last registered callback (bulk-bar reads it)
      return this._selChangeCbs[this._selChangeCbs.length - 1] || null;
    },
    set: function (cb) {
      if (typeof cb === "function") this._selChangeCbs.push(cb);
    }
  });

  CardsFeed.prototype._fireSelChange = function () {
    var sel = this.getSelection();
    for (var i = 0; i < this._selChangeCbs.length; i++) {
      try { this._selChangeCbs[i](sel); } catch (e) { /* ignore */ }
    }
  };

  // ─── Bulk-bar compatibility shims ────────────────────────────────────────

  CardsFeed.prototype.markFailedRows = function (ids) {
    // Best-effort: highlight failed cards
    var self = this;
    ids.forEach(function (id) {
      var card = self._container.querySelector('[data-cf-id="' + id + '"]');
      if (card) {
        card.classList.add("cf-card--error");
        setTimeout(function () { card && card.classList.remove("cf-card--error"); }, 4000);
      }
    });
  };

  CardsFeed.prototype.buildFailureRows = function (failed) {
    var self = this;
    return failed.map(function (f) {
      var item = self._selected[f.id] || null;
      return { id: f.id, reason: f.reason, name: item ? self.getRowName(item) : null };
    });
  };

  // ─── Load ─────────────────────────────────────────────────────────────────

  CardsFeed.prototype.load = function (opts) {
    opts = opts || {};
    if (opts.page) this._page = opts.page;
    var self = this;
    self._setLoading(true);

    var params = new URLSearchParams();
    params.set("page",     self._page);
    params.set("limit",    self._limit);
    if (self._sortBy) {
      params.set("sort_by",  self._sortBy);
      params.set("sort_dir", self._sortDir);
    }
    if (self._query) params.set("q", self._query);

    var filters = Object.assign({}, self._filters);
    Object.keys(filters).forEach(function (k) {
      params.set(k, filters[k]);
    });

    var url = self.endpoint + "?" + params.toString();

    var useApi = typeof global.api !== "undefined" && typeof global.api.get === "function";
    var promise;
    if (useApi) {
      promise = global.api.get(url);
    } else {
      promise = fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) { return r.json(); });
    }

    return promise.then(function (data) {
      if (!data || data._failed) {
        // Surface failure: render empty state + clear count via onLoad.
        self._data = { items: [], total: 0, page: self._page, limit: self._limit };
        self._renderCards();
        self._renderPager();
        self._setLoading(false);
        if (self._onLoadCb) self._onLoadCb(self._data);
        return;
      }
      self._data = {
        items: data.items || [],
        total: data.total || 0,
        page:  data.page  || self._page,
        limit: data.limit || self._limit,
      };
      self._renderCards();
      self._renderPager();
      self._setLoading(false);
      if (self._onLoadCb) self._onLoadCb(self._data);
    }).catch(function (err) {
      console.error("[CardsFeed] load error", err);
      self._data = { items: [], total: 0, page: self._page, limit: self._limit };
      self._renderCards();
      self._renderPager();
      self._setLoading(false);
      if (self._onLoadCb) self._onLoadCb(self._data);
    });
  };

  // ─── Build DOM ───────────────────────────────────────────────────────────

  CardsFeed.prototype._build = function () {
    var self = this;
    var root = document.getElementById(self.containerId);
    if (!root) { console.error("[CardsFeed] container not found:", self.containerId); return; }

    root.innerHTML = "";
    root.classList.add("cf-root");

    // Toolbar
    var toolbar = document.createElement("div");
    toolbar.className = "cf-toolbar";

    // Status filter
    var statusSel = document.createElement("select");
    statusSel.className = "cf-toolbar__select";
    statusSel.dataset.role = "status-filter";
    statusSel.innerHTML =
      '<option value="">Все статусы</option>' +
      self._statusOptions().map(function (o) {
        return '<option value="' + esc(o.value) + '">' + esc(o.label) + '</option>';
      }).join("");
    statusSel.addEventListener("change", function () {
      if (statusSel.value) {
        self._filters["status__eq"] = statusSel.value;
      } else {
        delete self._filters["status__eq"];
      }
      self._page = 1;
      self.load();
    });
    toolbar.appendChild(statusSel);

    // Search
    var searchInput = document.createElement("input");
    searchInput.type = "search";
    searchInput.className = "cf-toolbar__search";
    searchInput.placeholder = "Поиск…";
    searchInput.dataset.role = "search";
    var doSearch = debounce(function () {
      self._query = searchInput.value.trim();
      self._page = 1;
      self.load();
    }, 300);
    searchInput.addEventListener("input", doSearch);
    toolbar.appendChild(searchInput);

    // Sort
    var sortSel = document.createElement("select");
    sortSel.className = "cf-toolbar__select";
    sortSel.dataset.role = "sort";
    sortSel.innerHTML =
      '<option value="created_at|desc">Сначала новые</option>' +
      '<option value="created_at|asc">Сначала старые</option>' +
      '<option value="id|desc">ID убыв.</option>' +
      '<option value="id|asc">ID возр.</option>';
    sortSel.addEventListener("change", function () {
      var parts = sortSel.value.split("|");
      self._sortBy  = parts[0];
      self._sortDir = parts[1] || "desc";
      self._page = 1;
      self.load();
    });
    toolbar.appendChild(sortSel);

    // Archive toggle
    var archiveBtn = document.createElement("button");
    archiveBtn.type = "button";
    archiveBtn.className = "btn btn--ghost btn--sm";
    archiveBtn.dataset.role = "archive-toggle";
    archiveBtn.textContent = "Показать архив";
    archiveBtn.addEventListener("click", function () {
      self._showAll = !self._showAll;
      if (self._showAll) {
        delete self._filters["status__neq"];
        archiveBtn.textContent = "Только активные";
        archiveBtn.classList.add("btn--active");
      } else {
        if (self.initialFilters["status__neq"]) {
          self._filters["status__neq"] = self.initialFilters["status__neq"];
        }
        archiveBtn.textContent = "Показать архив";
        archiveBtn.classList.remove("btn--active");
      }
      self._page = 1;
      self.load();
    });
    toolbar.appendChild(archiveBtn);

    root.appendChild(toolbar);

    // Cards area
    var cardsArea = document.createElement("div");
    cardsArea.className = "cf-cards";
    cardsArea.dataset.role = "cards";
    root.appendChild(cardsArea);

    // Pager
    var pager = document.createElement("div");
    pager.className = "cf-pager";
    pager.dataset.role = "pager";
    root.appendChild(pager);

    // Drawer
    var drawer = document.createElement("div");
    drawer.className = "cf-drawer";
    drawer.dataset.role = "drawer";
    drawer.innerHTML = '<button class="cf-drawer__close" type="button" aria-label="Закрыть">&times;</button><div class="cf-drawer__body" data-role="drawer-body"></div>';
    drawer.querySelector(".cf-drawer__close").addEventListener("click", function () { self._closeDrawer(); });
    document.body.appendChild(drawer);
    self._drawer = drawer;

    // Close drawer on outside click / Escape
    document.addEventListener("click", function (e) {
      if (drawer.classList.contains("cf-drawer--open") && !drawer.contains(e.target)) {
        var card = e.target.closest(".cf-card");
        if (!card || !card.querySelector('[data-role="drawer-btn"]')) {
          self._closeDrawer();
        }
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") self._closeDrawer();
    });

    self._container = root;
  };

  CardsFeed.prototype._statusOptions = function () {
    // Subclasses or wiring can override by setting self._statusOptionsList
    return this._statusOptionsList || [];
  };

  // ─── Render ──────────────────────────────────────────────────────────────

  CardsFeed.prototype._renderCards = function () {
    var self = this;
    var area = self._container.querySelector('[data-role="cards"]');
    if (!area) return;

    var items = self._data.items;
    if (!items || items.length === 0) {
      area.innerHTML = '<div class="cf-empty">Ничего не найдено</div>';
      return;
    }

    area.innerHTML = "";
    items.forEach(function (item) {
      var id = item[self.rowIdKey];
      var card = document.createElement("div");
      card.className = "cf-card";
      if (self._selected[id]) card.classList.add("cf-card--selected");
      card.dataset.cfId = String(id);

      var inner = "";

      // Checkbox
      if (self.selectable) {
        var checked = self._selected[id] ? " checked" : "";
        inner += '<label class="cf-card__check"><input type="checkbox" data-role="select"' + checked + ' aria-label="Выбрать"></label>';
      }

      // Body
      inner += '<div class="cf-card__content">' + self.renderCard(item) + '</div>';

      // Inline actions zone (renderCardActions) and/or drawer button
      if (self.renderCardActions) {
        var actionsHtml = self.renderCardActions(item) || "";
        if (actionsHtml) {
          inner += '<div class="cf-card__actions" data-role="actions">' + actionsHtml + '</div>';
        }
      }
      if (self.showDrawerBtn) {
        inner += '<button type="button" class="btn btn--ghost btn--sm cf-card__drawer-btn" data-role="drawer-btn">Детали</button>';
      }

      card.innerHTML = inner;

      // Checkbox handler
      if (self.selectable) {
        var cb = card.querySelector('[data-role="select"]');
        cb.addEventListener("change", function () {
          if (cb.checked) {
            self._selected[id] = item;
            card.classList.add("cf-card--selected");
          } else {
            delete self._selected[id];
            card.classList.remove("cf-card--selected");
          }
          self._fireSelChange();
        });
      }

      // Drawer handler
      if (self.showDrawerBtn) {
        var drawerBtn = card.querySelector('[data-role="drawer-btn"]');
        if (drawerBtn) {
          drawerBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            self._openDrawer(item);
          });
        }
      }

      // Inline-action delegated handler
      if (self.onActionClick) {
        var actionsZone = card.querySelector('[data-role="actions"]');
        if (actionsZone) {
          actionsZone.addEventListener("click", function (e) {
            var target = e.target.closest("[data-action]");
            if (!target || target.disabled) return;
            e.preventDefault();
            e.stopPropagation();
            self.onActionClick(item, target.getAttribute("data-action"), target);
          });
        }
      }

      area.appendChild(card);
    });
  };

  CardsFeed.prototype._renderPager = function () {
    var self = this;
    var pager = self._container.querySelector('[data-role="pager"]');
    if (!pager) return;

    var total = self._data.total;
    var limit = self._limit;
    var page  = self._page;
    var pages = Math.max(1, Math.ceil(total / limit));

    pager.innerHTML = "";
    if (pages <= 1 && total === 0) return;

    var prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "btn btn--ghost btn--sm";
    prevBtn.textContent = "← Пред";
    prevBtn.disabled = (page <= 1);
    prevBtn.addEventListener("click", function () {
      if (self._page > 1) { self._page--; self.load(); }
    });

    var info = document.createElement("span");
    info.className = "cf-pager__info";
    info.textContent = "Стр. " + page + " из " + pages + " (" + total + " записей)";

    var nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "btn btn--ghost btn--sm";
    nextBtn.textContent = "След →";
    nextBtn.disabled = (page >= pages);
    nextBtn.addEventListener("click", function () {
      if (self._page < pages) { self._page++; self.load(); }
    });

    pager.appendChild(prevBtn);
    pager.appendChild(info);
    pager.appendChild(nextBtn);
  };

  CardsFeed.prototype._setLoading = function (on) {
    this._loading = on;
    var area = this._container && this._container.querySelector('[data-role="cards"]');
    if (!area) return;
    if (on) {
      area.classList.add("cf-cards--loading");
    } else {
      area.classList.remove("cf-cards--loading");
    }
  };

  // ─── Drawer ──────────────────────────────────────────────────────────────

  CardsFeed.prototype._openDrawer = function (item) {
    var body = this._drawer.querySelector('[data-role="drawer-body"]');
    body.innerHTML = this._renderDrawerContent(item);
    this._drawer.classList.add("cf-drawer--open");
  };

  CardsFeed.prototype._closeDrawer = function () {
    if (this._drawer) this._drawer.classList.remove("cf-drawer--open");
  };

  CardsFeed.prototype._renderDrawerContent = function (item) {
    var html = '<table class="cf-drawer__table">';
    Object.keys(item).forEach(function (k) {
      var v = item[k];
      if (v !== null && typeof v === "object") v = JSON.stringify(v, null, 2);
      html += "<tr><th>" + esc(k) + "</th><td><pre>" + esc(String(v == null ? "—" : v)) + "</pre></td></tr>";
    });
    html += "</table>";
    return html;
  };

  global.CardsFeed = CardsFeed;
})(window);
