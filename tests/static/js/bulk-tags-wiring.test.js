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
    ["static/js/bulk-tags-wiring.js"],
    {
      BulkActionBar: FakeBulkActionBar,
      api,
      bulkFmtNumber: (n) => String(n),
      ...(extraGlobals || {}),
    },
  );
  return { ...env, captured, apiCalls, api };
}

test("mountTagsBulkBar returns null when table is null", () => {
  const { sandbox, captured } = setupWiring();
  const result = sandbox.mountTagsBulkBar(null);
  assert.equal(result, null);
  assert.equal(captured.args, null);
});

test("mountTagsBulkBar returns null when table is undefined", () => {
  const { sandbox, captured } = setupWiring();
  const result = sandbox.mountTagsBulkBar(undefined);
  assert.equal(result, null);
  assert.equal(captured.args, null);
});

test("mountTagsBulkBar registers 3 actions with stable ids in order", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountTagsBulkBar({ /* fake table */ });
  const ids = captured.args.actions.map(a => a.id);
  assert.deepEqual(plain(ids), ["activate", "deactivate", "delete"]);
});

test("activate action has confirm 'soft' and icon 'check-circle'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountTagsBulkBar({});
  const byId = Object.fromEntries(captured.args.actions.map(a => [a.id, a]));
  assert.equal(byId.activate.confirm, "soft");
  assert.equal(byId.activate.icon, "check-circle");
});

test("deactivate action has confirm 'soft' and icon 'circle-off'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountTagsBulkBar({});
  const byId = Object.fromEntries(captured.args.actions.map(a => [a.id, a]));
  assert.equal(byId.deactivate.confirm, "soft");
  assert.equal(byId.deactivate.icon, "circle-off");
});

test("delete action is type-to-confirm with danger variant and typeWord 'удалить'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountTagsBulkBar({});
  const del = captured.args.actions.find(a => a.id === "delete");
  assert.equal(del.confirm, "type-to-confirm");
  assert.equal(del.variant, "danger");
  assert.equal(del.typeWord, "удалить");
});

test("activate handler POSTs to /admin/tags/bulk/activate with active=true", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountTagsBulkBar({});
  const activate = captured.args.actions.find(a => a.id === "activate");
  const payload = { target: { kind: "ids", ids: [1, 2] } };
  await activate.handler(payload);
  assert.equal(apiCalls.length, 1);
  assert.equal(apiCalls[0].url, "/admin/tags/bulk/activate");
  assert.deepEqual(plain(apiCalls[0].body), { target: { kind: "ids", ids: [1, 2] }, active: true });
});

test("deactivate handler POSTs to /admin/tags/bulk/activate with active=false", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountTagsBulkBar({});
  const deactivate = captured.args.actions.find(a => a.id === "deactivate");
  await deactivate.handler({ target: { kind: "filter", filter: {} } });
  assert.equal(apiCalls[0].url, "/admin/tags/bulk/activate");
  assert.equal(apiCalls[0].body.active, false);
});

test("delete handler POSTs to /admin/tags/bulk/delete with payload as-is", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountTagsBulkBar({});
  const del = captured.args.actions.find(a => a.id === "delete");
  const payload = { target: { kind: "ids", ids: [7] } };
  await del.handler(payload);
  assert.equal(apiCalls[0].url, "/admin/tags/bulk/delete");
  assert.deepEqual(plain(apiCalls[0].body), plain(payload));
});

test("handler returns {cancelled:true} when api.post returns {_failed:true}", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountTagsBulkBar({});
  apiCalls.__nextResult = { _failed: true, error: "boom" };
  const activate = captured.args.actions.find(a => a.id === "activate");
  const result = await activate.handler({ target: { kind: "ids", ids: [1] } });
  assert.deepEqual(plain(result), { cancelled: true });
});

test("delete confirmText includes selection total and 'необратимо'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountTagsBulkBar({});
  const del = captured.args.actions.find(a => a.id === "delete");
  const text = del.confirmText({ total: 42 });
  assert.ok(text.includes("42"));
  assert.ok(text.includes("необратимо"));
});

test("getRowName returns tag title", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountTagsBulkBar({});
  assert.equal(captured.args.getRowName({ id: 1, title: "Новинка" }), "Новинка");
});
