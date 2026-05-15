"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadBrowserScripts } = require("./_harness.js");

// Cross-context arrays/objects have different prototypes; normalize before
// structural comparison so deepEqual does not reject on prototype identity.
function plain(x) { return JSON.parse(JSON.stringify(x)); }

function makeTable(items, total) {
  const env = loadBrowserScripts([
    "static/js/bulk-i18n.js",
    "static/js/smart-table.js",
  ]);
  const { sandbox } = env;
  const calls = [];
  const SmartTable = sandbox.SmartTable;
  const table = new SmartTable({
    instanceName: "t",
    endpoint: "/x",
    schemaEndpoint: null,
    containerId: "c",
    columns: [{ key: "id", label: "ID", sortable: false }],
    selectable: true,
    rowIdKey: "id",
    onSelectionChange: (sel) => calls.push(JSON.parse(JSON.stringify(sel))),
  });
  table.lastData = {
    items: items.map(it => ({ id: it })),
    total: total != null ? total : items.length,
  };
  // No-op render to keep tests focused on state transitions.
  table.render = () => {};
  // No-op load so reset hooks do not trigger HTTP.
  table.load = async () => {};
  return { table, calls, sandbox, env };
}

test("initial state is empty", () => {
  const { table } = makeTable(["a", "b", "c"]);
  assert.equal(table.selection.mode, "empty");
  const sel = plain(table.getSelection());
  assert.deepEqual(sel, { mode: "empty", total: 0 });
});

test("toggleRow adds id, second toggle removes it back to empty", () => {
  const { table, calls } = makeTable(["a", "b"]);
  table.toggleRow("a", 0, false);
  assert.equal(table.selection.mode, "ids");
  assert.deepEqual([...table.selection.ids], ["a"]);
  assert.equal(calls.at(-1).mode, "ids");
  assert.equal(calls.at(-1).total, 1);

  table.toggleRow("a", 0, false);
  assert.equal(table.selection.mode, "empty");
  assert.equal(table.selection.ids.size, 0);
  assert.equal(calls.at(-1).mode, "empty");
});

test("selectPage selects every id on the current page", () => {
  const { table } = makeTable(["a", "b", "c"], 30);
  table.selectPage();
  const sel = plain(table.getSelection());
  assert.equal(sel.mode, "ids");
  assert.deepEqual(sel.ids.sort(), ["a", "b", "c"]);
  assert.equal(sel.total, 3);
});

test("selectAllByFilter switches to filter mode and clears ids", () => {
  const { table } = makeTable(["a", "b"], 100);
  table.selectPage();
  table.selectAllByFilter();
  const sel = plain(table.getSelection());
  assert.equal(sel.mode, "all_by_filter");
  assert.deepEqual(sel.filter, {});
  assert.equal(sel.total, 100);
  assert.equal(table.selection.ids.size, 0);
});

test("Shift+click selects an inclusive range", () => {
  const { table } = makeTable(["a", "b", "c", "d"]);
  table.toggleRow("a", 0, false);
  // Shift-click on idx 2 → expect range a..c selected.
  table.toggleRow("c", 2, true);
  assert.deepEqual([...table.selection.ids].sort(), ["a", "b", "c"]);
  assert.equal(table.selection.mode, "ids");
});

test("clearSelection drops to empty and fires callback", () => {
  const { table, calls } = makeTable(["a", "b"]);
  table.selectPage();
  table.clearSelection();
  assert.equal(table.selection.mode, "empty");
  assert.equal(calls.at(-1).mode, "empty");
});

test("filter change while in all_by_filter dispatches reset toast", () => {
  const { table, env } = makeTable(["a"], 100);
  table.selectAllByFilter();
  env.doc.body._events.length = 0;
  table.applyFilter("name", "eq", "x", "Имя");
  const toasts = env.doc.body._events.filter(e => e.type === "showToast");
  assert.equal(toasts.length, 1);
  assert.match(toasts[0].detail.message, /Выделение сброшено/);
  assert.equal(table.selection.mode, "empty");
});

test("sort change in ids mode resets silently (no toast)", () => {
  const { table, env } = makeTable(["a", "b"]);
  table.toggleRow("a", 0, false);
  env.doc.body._events.length = 0;
  table.handleSort("id");
  const toasts = env.doc.body._events.filter(e => e.type === "showToast");
  assert.equal(toasts.length, 0);
  assert.equal(table.selection.mode, "empty");
});

test("page change preserves all_by_filter", () => {
  const { table } = makeTable(["a", "b"], 100);
  table.selectAllByFilter();
  table.setPage(2);
  assert.equal(table.selection.mode, "all_by_filter");
});

test("page change in ids mode silently resets", () => {
  const { table, env } = makeTable(["a", "b"], 100);
  table.toggleRow("a", 0, false);
  env.doc.body._events.length = 0;
  table.setPage(2);
  assert.equal(table.selection.mode, "empty");
  const toasts = env.doc.body._events.filter(e => e.type === "showToast");
  assert.equal(toasts.length, 0);
});

test("HTMX rebuild (setStaticFilters) emits one-shot session hint", () => {
  const { table, env } = makeTable(["a"], 1);
  table.toggleRow("a", 0, false);
  env.doc.body._events.length = 0;
  table.setStaticFilters([{ key: "category_id", op: "eq", val: "5" }]);
  const toasts1 = env.doc.body._events.filter(e => e.type === "showToast");
  assert.equal(toasts1.length, 1);
  assert.match(toasts1[0].detail.message, /Выделение сброшено/);

  // Second rebuild within the same session must NOT toast again.
  table.toggleRow("a", 0, false);
  env.doc.body._events.length = 0;
  table.setStaticFilters([{ key: "category_id", op: "eq", val: "6" }]);
  const toasts2 = env.doc.body._events.filter(e => e.type === "showToast");
  assert.equal(toasts2.length, 0);
});

test("toggleRow on all_by_filter row drops back to ids minus that id", () => {
  const { table } = makeTable(["a", "b", "c"], 3);
  table.selectAllByFilter();
  // Untick 'b' — bar should now be in ids mode with {a, c}.
  table.toggleRow("b", 1, false);
  assert.equal(table.selection.mode, "ids");
  assert.deepEqual([...table.selection.ids].sort(), ["a", "c"]);
});

test("getSelection returns ids array, not Set", () => {
  const { table } = makeTable(["a", "b"]);
  table.toggleRow("a", 0, false);
  table.toggleRow("b", 1, false);
  const sel = table.getSelection();
  assert.ok(Array.isArray(sel.ids));
  assert.equal(sel.ids.length, 2);
});

test("destroy removes document listeners and clears selection", () => {
  const { table, env } = makeTable(["a"]);
  table.toggleRow("a", 0, false);
  const before = env.doc._listeners.click.length + env.doc._listeners.keydown.length;
  table.destroy();
  const after = env.doc._listeners.click.length + env.doc._listeners.keydown.length;
  assert.equal(after, before - 2);
  assert.equal(table.selection.mode, "empty");
});

test("buildFailureRows enriches with name via getRowName", () => {
  const { table } = makeTable([]);
  table.lastData = { items: [{ id: "a", title: "Foo" }, { id: "b", title: "Bar" }], total: 2 };
  table.getRowName = (it) => it.title;
  const rows = table.buildFailureRows([
    { id: "a", reason: "tag_in_use" },
    { id: "c", reason: "not_found" },
  ]);
  assert.equal(rows[0].name, "Foo");
  assert.equal(rows[1].name, null);
});
