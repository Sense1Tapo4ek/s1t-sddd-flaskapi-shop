"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const { loadBrowserScripts } = require("./_harness");

// vm contexts have their own Array prototype; assert.deepEqual rejects
// cross-context objects. Normalize via JSON round-trip.
const plain = (x) => JSON.parse(JSON.stringify(x));

function setupWiring(extraGlobals) {
  // Mock BulkActionBar — capture constructor args so we can introspect actions.
  const captured = { args: null };
  class FakeBulkActionBar {
    constructor(args) { captured.args = args; this.actions = args.actions; }
  }
  const apiCalls = [];
  const api = {
    post: async (url, body) => {
      apiCalls.push({ url, body });
      return apiCalls.__nextResult || { total: 1, ok: 1, failed: [] };
    },
    get: async () => ({}),
  };
  const env = loadBrowserScripts(
    ["static/js/bulk-products-wiring.js"],
    {
      BulkActionBar: FakeBulkActionBar,
      api,
      bulkFmtNumber: (n) => String(n),
      ...(extraGlobals || {}),
    },
  );
  return { ...env, captured, apiCalls, api };
}

test("mountProductsBulkBar returns null when table is null", () => {
  const { sandbox, captured } = setupWiring();
  const result = sandbox.mountProductsBulkBar(null);
  assert.equal(result, null);
  assert.equal(captured.args, null);
});

test("mountProductsBulkBar registers 5 actions with stable ids", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountProductsBulkBar({ /* fake table */ });
  const ids = captured.args.actions.map(a => a.id);
  assert.deepEqual(plain(ids), ["activate", "deactivate", "category", "tags", "delete"]);
});

test("activate / deactivate actions are soft-confirm with correct icons", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountProductsBulkBar({});
  const byId = Object.fromEntries(captured.args.actions.map(a => [a.id, a]));
  assert.equal(byId.activate.confirm, "soft");
  assert.equal(byId.activate.icon, "check-circle");
  assert.equal(byId.deactivate.confirm, "soft");
  assert.equal(byId.deactivate.icon, "circle-off");
});

test("delete action is type-to-confirm with danger variant and word 'удалить'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountProductsBulkBar({});
  const del = captured.args.actions.find(a => a.id === "delete");
  assert.equal(del.confirm, "type-to-confirm");
  assert.equal(del.variant, "danger");
  assert.equal(del.typeWord, "удалить");
});

test("activate handler POSTs to /admin/products/bulk/activate with active=true", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountProductsBulkBar({});
  const activate = captured.args.actions.find(a => a.id === "activate");
  const payload = { target: { kind: "ids", ids: [1, 2] } };
  await activate.handler(payload);
  assert.equal(apiCalls.length, 1);
  assert.equal(apiCalls[0].url, "/admin/products/bulk/activate");
  assert.deepEqual(plain(apiCalls[0].body), { target: { kind: "ids", ids: [1, 2] }, active: true });
});

test("deactivate handler POSTs with active=false", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountProductsBulkBar({});
  const deactivate = captured.args.actions.find(a => a.id === "deactivate");
  await deactivate.handler({ target: { kind: "filter", filter: {} } });
  assert.equal(apiCalls[0].body.active, false);
});

test("delete handler POSTs to /admin/products/bulk/delete with payload as-is", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountProductsBulkBar({});
  const del = captured.args.actions.find(a => a.id === "delete");
  const payload = { target: { kind: "ids", ids: [7] } };
  await del.handler(payload);
  assert.equal(apiCalls[0].url, "/admin/products/bulk/delete");
  assert.deepEqual(plain(apiCalls[0].body), plain(payload));
});

test("handler returns {cancelled:true} when api.post fails", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountProductsBulkBar({});
  apiCalls.__nextResult = { _failed: true, error: "boom" };
  const activate = captured.args.actions.find(a => a.id === "activate");
  const result = await activate.handler({ target: { kind: "ids", ids: [1] } });
  assert.deepEqual(plain(result), { cancelled: true });
});

test("delete confirmText interpolates selection total", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountProductsBulkBar({});
  const del = captured.args.actions.find(a => a.id === "delete");
  const text = del.confirmText({ total: 42 });
  assert.ok(text.includes("42"));
  assert.ok(text.includes("необратимо"));
});

test("category and tags actions use confirm:none (custom modal in handler)", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountProductsBulkBar({});
  const byId = Object.fromEntries(captured.args.actions.map(a => [a.id, a]));
  assert.equal(byId.category.confirm, "none");
  assert.equal(byId.tags.confirm, "none");
});

test("getRowName is wired and returns product title", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountProductsBulkBar({});
  assert.equal(captured.args.getRowName({ id: 1, title: "Книга" }), "Книга");
});
