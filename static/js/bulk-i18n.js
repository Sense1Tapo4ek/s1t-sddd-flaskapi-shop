/* Bulk-actions UI strings (RU). Spec §4.5 — single source of truth.
   Use bulkT("bulk.count", {n: 12}) for interpolation. */

(function (global) {
  "use strict";

  const STRINGS = {
    // ─── Bar + counters ───────────────────────────────────────────────
    "bulk.count":               "Выбрано: {n}",
    "bulk.clear":               "Снять выделение",
    "bulk.master.page":         "Выделить страницу ({n})",
    "bulk.master.all":          "Выделить всё ({total})",
    "bulk.master.unselect":     "Снять выделение",
    "bulk.allSelected":         "Выбрано все {total} по фильтру.",
    "bulk.filterChanged":       "Выделение сброшено: фильтр изменён.",
    "bulk.htmxReset.hint":      "Выделение сброшено. Используйте «Выделить всё», чтобы сохранять выбор между категориями.",

    // ─── Unified action modal ─────────────────────────────────────────
    "bulk.modal.cancel":        "Отмена",
    "bulk.modal.primary":       "{label} ({n})",
    "bulk.scope.ids":           "Операция будет выполнена для {n} выбранных объектов.",
    "bulk.scope.filter":        "Операция будет выполнена для {n} объектов, подходящих под текущий фильтр. Список будет доступен в результате.",

    // ─── Lifecycle ────────────────────────────────────────────────────
    "bulk.beforeUnload":        "Операция выполняется. Закрыть страницу?",
    "bulk.actionInProgress":    "Выполняется…",
    "bulk.actionDone":          "Готово: затронуто {n}",
    "bulk.actionPartial.title": "Готово: {ok} из {total}",
    "bulk.actionPartial.sub":   "{failed} не удалось обработать.",
    "bulk.actionPartial.details":"Показать подробности",
    "bulk.actionFailed":        "Не удалось выполнить операцию",

    // ─── Failures-detail modal ────────────────────────────────────────
    "bulk.failures.title":      "Не удалось обработать",
    "bulk.failures.col.name":   "Название",
    "bulk.failures.col.id":     "ID",
    "bulk.failures.col.reason": "Причина",
    "bulk.failures.close":      "Закрыть",

    // ─── Action labels (used in bar buttons and modal headers) ────────
    "bulk.btn.activate":        "Активировать",
    "bulk.btn.deactivate":      "Деактивировать",
    "bulk.btn.delete":          "Удалить",
    "bulk.btn.cancel":          "Отмена",
    "bulk.btn.apply":           "Применить",
    "bulk.btn.assign":          "Назначить",

    // ─── Products ─────────────────────────────────────────────────────
    "bulk.products.action.category":         "Категория",
    "bulk.products.action.tags":             "Теги",

    "bulk.products.modal.category.title":    "Перенести в категорию",
    "bulk.products.modal.category.help":     "Выберите конечную категорию. Промежуточные узлы дерева недоступны.",
    "bulk.products.modal.category.search":   "Поиск категории…",
    "bulk.products.modal.category.notLeaf":  "не конечная",
    "bulk.products.modal.tags.title":        "Изменить теги",
    "bulk.products.modal.tags.modeLegend":   "Режим",
    "bulk.products.modal.tags.mode.add":     "Добавить (сохранить старые)",
    "bulk.products.modal.tags.mode.remove":  "Убрать выбранные",
    "bulk.products.modal.tags.mode.replace": "Заменить весь набор",

    "bulk.products.confirm.deleteTitle":     "Удалить товары",
    "bulk.products.confirm.deleteText":      "Будет удалено {n} товаров. Действие необратимо: файлы изображений будут стёрты, а позиции в существующих заказах помечены как удалённые.",

    "bulk.products.explain.activate":        "Выбранные товары станут видимыми в каталоге. Уже активные не изменятся.",
    "bulk.products.explain.deactivate":      "Выбранные товары перестанут показываться в публичном каталоге. В админке они останутся.",
    "bulk.products.explain.category":        "Все выбранные товары будут перенесены в новую конечную категорию. Прошлая категория заменится.",
    "bulk.products.explain.tags.add":        "Выбранные теги будут добавлены к товарам. Уже стоящие теги сохранятся.",
    "bulk.products.explain.tags.remove":     "Выбранные теги будут сняты с товаров. Остальные теги сохранятся.",
    "bulk.products.explain.tags.replace":    "Набор тегов у выбранных товаров будет полностью заменён. Старые теги пропадут.",

    // ─── Tags ─────────────────────────────────────────────────────────
    "bulk.tags.confirm.deleteTitle":         "Удалить теги",
    "bulk.tags.confirm.deleteText":          "Будет удалено {n} тегов. Действие необратимо. Теги, использованные хотя бы в одном товаре, будут пропущены.",

    "bulk.tags.explain.activate":            "Выбранные теги станут видимыми в каталоге.",
    "bulk.tags.explain.deactivate":          "Выбранные теги перестанут показываться в каталоге. Привязка к товарам сохранится.",

    // ─── Orders ───────────────────────────────────────────────────────
    "bulk.orders.action.status":             "Изменить статус",
    "bulk.orders.modal.statusTitle":         "Изменить статус заказов",
    "bulk.orders.modal.statusLegend":        "Новый статус",
    "bulk.orders.status.new":                "Новый",
    "bulk.orders.status.processing":         "В обработке",
    "bulk.orders.status.done":               "Выполнен",
    "bulk.orders.status.canceled":           "Отменён",
    "bulk.orders.explain.status":            "Выбранным заказам будет назначен новый статус. Недопустимые переходы будут отклонены.",

    // ─── Generic ──────────────────────────────────────────────────────
    "bulk.search.placeholder":               "Поиск…",
    "bulk.empty.notFound":                   "Ничего не найдено",
  };

  // Stable error codes mapped to RU labels. Unknown codes fall back to raw value.
  const REASONS = {
    "bulk_target_empty":            "Список пуст",
    "bulk_target_too_large":        "Превышен лимит (≤1000)",
    "product_in_use_by_active_order":"В активном заказе",
    "tag_in_use":                   "Тег используется в товаре",
    "illegal_transition":           "Недопустимый переход статуса",
    "order_already_terminal":       "Заказ в финальном статусе",
    "not_found":                    "Не найдено",
    "PRODUCT_NOT_FOUND":            "Товар не найден",
    "TAG_NOT_FOUND":                "Тег не найден",
    "CATEGORY_NOT_FOUND":           "Категория не найдена",
    "ORDER_NOT_FOUND":              "Заказ не найден",
    "INVALID_TRANSITION":           "Недопустимый переход статуса",
    "forbidden":                    "Запрещено",
    "validation_error":             "Ошибка валидации",
  };

  function fmtNumber(n) {
    if (typeof n !== "number" || !isFinite(n)) return String(n);
    // Тонкие пробелы у тысяч: 1 234, 1 234 567 (U+202F narrow no-break).
    return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function bulkT(key, params) {
    let s = STRINGS[key] || key;
    if (!params) return s;
    return s.replace(/\{(\w+)\}/g, function (_, k) {
      const v = params[k];
      if (typeof v === "number") return fmtNumber(v);
      return v == null ? "" : String(v);
    });
  }

  function bulkReason(code) {
    return REASONS[code] || code || "—";
  }

  global.bulkT = bulkT;
  global.bulkReason = bulkReason;
  global.bulkFmtNumber = fmtNumber;
})(window);
