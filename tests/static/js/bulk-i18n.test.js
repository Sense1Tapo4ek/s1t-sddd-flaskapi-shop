"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadBrowserScripts } = require("./_harness.js");

// Narrow no-break space (U+202F) — the thousands separator the source uses.
const NBSP = " ";

function load() {
  return loadBrowserScripts(["static/js/bulk-i18n.js"]);
}

test("bulkT — returns plain string when no placeholders", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkT("bulk.clear"), "Снять выделение");
});

test("bulkT — falls back to key for unknown keys", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkT("nope.such.key"), "nope.such.key");
});

test("bulkT — interpolates {n} with formatted number", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkT("bulk.count", { n: 1234 }), `Выбрано: 1${NBSP}234`);
});

test("bulkT — interpolates {ok}, {total} together", () => {
  const { sandbox } = load();
  const s = sandbox.bulkT("bulk.actionPartial.title", { ok: 230, total: 234 });
  assert.equal(s, "Готово: 230 из 234");
});

test("bulkT — empty params yields empty replacement", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkT("bulk.count", {}), "Выбрано: ");
});

test("bulkReason — maps known code", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkReason("tag_in_use"), "Тег используется в товаре");
});

test("bulkReason — unknown code returned as-is", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkReason("weird_thing"), "weird_thing");
});

test("bulkReason — null/undefined → em-dash", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkReason(null), "—");
  assert.equal(sandbox.bulkReason(undefined), "—");
});

test("bulkFmtNumber — adds narrow no-break space at thousands boundaries", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkFmtNumber(0), "0");
  assert.equal(sandbox.bulkFmtNumber(999), "999");
  assert.equal(sandbox.bulkFmtNumber(1000), `1${NBSP}000`);
  assert.equal(sandbox.bulkFmtNumber(1234567), `1${NBSP}234${NBSP}567`);
});

test("bulkFmtNumber — non-finite gracefully stringified", () => {
  const { sandbox } = load();
  assert.equal(sandbox.bulkFmtNumber(NaN), "NaN");
  assert.equal(sandbox.bulkFmtNumber(Infinity), "Infinity");
});
