"use strict";

/**
 * Phase 6 — FE i18n cleanup contract tests (RED suite).
 *
 * Tests verify:
 *  1. New i18n keys resolve via bulkT() — will FAIL until bulk-i18n.js is extended.
 *  2. Wiring modules contain no hardcoded RU label literals — will FAIL until
 *     bulk-products-wiring.js, bulk-tags-wiring.js, bulk-orders-wiring.js are cleaned.
 */

const { test, describe } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { loadBrowserScripts, ROOT } = require("./_harness");

// ─── Helpers ──────────────────────────────────────────────────────────────────

function loadI18n() {
  return loadBrowserScripts(["static/js/bulk-i18n.js"]);
}

// ─── 1. i18n key coverage ─────────────────────────────────────────────────────

const REQUIRED_KEYS = [
  // Common buttons
  "bulk.btn.activate",
  "bulk.btn.deactivate",
  "bulk.btn.delete",
  "bulk.btn.cancel",
  "bulk.btn.apply",
  "bulk.btn.assign",

  // Products — action bar
  "bulk.products.action.category",
  "bulk.products.action.tags",

  // Products — category modal
  "bulk.products.modal.category.title",
  "bulk.products.modal.category.help",
  "bulk.products.modal.category.search",
  "bulk.products.modal.category.notLeaf",

  // Products — tags modal
  "bulk.products.modal.tags.title",
  "bulk.products.modal.tags.modeLegend",
  "bulk.products.modal.tags.mode.replace",
  "bulk.products.modal.tags.mode.add",
  "bulk.products.modal.tags.mode.remove",

  // Products — delete confirm
  "bulk.products.confirm.deleteTitle",
  "bulk.products.confirm.deleteText",

  // Tags — delete confirm
  "bulk.tags.confirm.deleteTitle",
  "bulk.tags.confirm.deleteText",

  // Orders
  "bulk.orders.action.status",
  "bulk.orders.modal.statusTitle",
  "bulk.orders.status.new",
  "bulk.orders.status.processing",
  "bulk.orders.status.done",
  "bulk.orders.status.canceled",

  // Generic
  "bulk.search.placeholder",
  "bulk.empty.notFound",
];

describe("bulk-i18n: every required key resolves", () => {
  const { sandbox } = loadI18n();

  for (const key of REQUIRED_KEYS) {
    test(`key "${key}" resolves to non-empty string different from the key itself`, () => {
      const result = sandbox.bulkT(key);
      assert.ok(
        typeof result === "string" && result.length > 0,
        `bulkT("${key}") returned empty or non-string: ${JSON.stringify(result)}`
      );
      assert.notEqual(
        result,
        key,
        `bulkT("${key}") fell back to the key itself — key is missing from STRINGS`
      );
    });
  }
});

test("bulk-i18n: products.confirm.deleteText interpolates n and contains 'необратимо'", () => {
  const { sandbox } = loadI18n();
  const result = sandbox.bulkT("bulk.products.confirm.deleteText", { n: 42 });
  assert.ok(result.includes("42"), `Expected "42" in: ${result}`);
  assert.ok(result.includes("необратимо"), `Expected "необратимо" in: ${result}`);
});

test("bulk-i18n: tags.confirm.deleteText interpolates n and contains 'необратимо'", () => {
  const { sandbox } = loadI18n();
  const result = sandbox.bulkT("bulk.tags.confirm.deleteText", { n: 42 });
  assert.ok(result.includes("42"), `Expected "42" in: ${result}`);
  assert.ok(result.includes("необратимо"), `Expected "необратимо" in: ${result}`);
});

// ─── 2. Wiring source: no hardcoded RU label literals ─────────────────────────
//
// Match only the quoted-literal form ("Строка") to avoid false positives in
// comments or identifiers.

test("wiring/products: source has no hardcoded RU label literals", () => {
  const src = fs.readFileSync(
    path.join(ROOT, "static/js/bulk-products-wiring.js"),
    "utf8"
  );

  const banned = [
    '"Активировать"',
    '"Деактивировать"',
    '"Категория"',
    '"Теги"',
    '"Удалить"',
    '"Назначить категорию"',
    '"Изменить теги"',
    '"Заменить"',
    '"Добавить"',
    '"Убрать"',
    '"Удалить выбранные товары?"',
    '"Поиск…"',
    '"Отмена"',
    '"Назначить"',
    '"Применить"',
    '"Действие необратимо"',
  ];

  for (const lit of banned) {
    assert.equal(
      src.includes(lit),
      false,
      `bulk-products-wiring.js still contains hardcoded literal: ${lit}`
    );
  }
});

test("wiring/tags: source has no hardcoded RU label literals", () => {
  const src = fs.readFileSync(
    path.join(ROOT, "static/js/bulk-tags-wiring.js"),
    "utf8"
  );

  const banned = [
    '"Активировать"',
    '"Деактивировать"',
    '"Удалить"',
    '"Удалить выбранные теги?"',
    '"Действие необратимо"',
  ];

  for (const lit of banned) {
    assert.equal(
      src.includes(lit),
      false,
      `bulk-tags-wiring.js still contains hardcoded literal: ${lit}`
    );
  }
});

test("wiring/orders: source has no hardcoded RU label literals", () => {
  const src = fs.readFileSync(
    path.join(ROOT, "static/js/bulk-orders-wiring.js"),
    "utf8"
  );

  const banned = [
    '"Изменить статус"',
    '"Изменить статус заказов"',
    '"Новый"',
    '"В обработке"',
    '"Выполнен"',
    '"Отменён"',
  ];

  for (const lit of banned) {
    assert.equal(
      src.includes(lit),
      false,
      `bulk-orders-wiring.js still contains hardcoded literal: ${lit}`
    );
  }
});
