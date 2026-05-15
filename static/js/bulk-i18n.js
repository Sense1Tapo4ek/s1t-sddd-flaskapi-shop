/* Bulk-actions UI strings (RU). Spec §4.5 — single source of truth.
   Use bulkT("bulk.count", {n: 12}) for interpolation. */

(function (global) {
  "use strict";

  const STRINGS = {
    "bulk.count":               "Выбрано: {n}",
    "bulk.clear":               "Снять выделение",
    "bulk.master.page":         "Выделить страницу ({n})",
    "bulk.master.all":          "Выделить всё ({total})",
    "bulk.master.unselect":     "Снять выделение",
    "bulk.allSelected":         "Выбрано все {total} по фильтру.",
    "bulk.filterChanged":       "Выделение сброшено: фильтр изменён.",
    "bulk.htmxReset.hint":      "Выделение сброшено. Используйте «Выделить всё», чтобы сохранять выбор между категориями.",
    "bulk.confirm.softPrompt":  "Подтвердите",
    "bulk.confirm.modalTitle":  "Подтвердите действие",
    "bulk.confirm.modalConfirm":"Да, выполнить",
    "bulk.confirm.modalCancel": "Отмена",
    "bulk.confirm.type.title":  "Подтвердите удаление",
    "bulk.confirm.type.hint":   "Чтобы подтвердить, введите слово:",
    "bulk.confirm.type.button": "Удалить {n}",
    "bulk.confirm.type.word":   "удалить",
    "bulk.beforeUnload":        "Операция выполняется. Закрыть страницу?",
    "bulk.actionInProgress":    "Выполняется…",
    "bulk.actionDone":          "Готово: затронуто {n}",
    "bulk.actionPartial.title": "Готово: {ok} из {total}",
    "bulk.actionPartial.sub":   "{failed} не удалось обработать.",
    "bulk.actionPartial.details":"Показать подробности",
    "bulk.actionFailed":        "Не удалось выполнить операцию",
    "bulk.failures.title":      "Не удалось обработать",
    "bulk.failures.col.name":   "Название",
    "bulk.failures.col.id":     "ID",
    "bulk.failures.col.reason": "Причина",
    "bulk.failures.close":      "Закрыть",
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
    "forbidden":                    "Запрещено",
    "validation_error":             "Ошибка валидации",
  };

  function fmtNumber(n) {
    if (typeof n !== "number" || !isFinite(n)) return String(n);
    // Тонкие пробелы у тысяч: 1 234, 1 234 567.
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
