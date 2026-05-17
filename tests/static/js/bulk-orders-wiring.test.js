"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const { loadBrowserScripts } = require("./_harness");

// vm contexts have their own Array prototype; assert.deepEqual rejects
// cross-context objects. Normalize via JSON round-trip.
const plain = (x) => JSON.parse(JSON.stringify(x));

function setupWiring(extraGlobals) {
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
    ["static/js/bulk-i18n.js", "static/js/bulk-orders-wiring.js"],
    {
      BulkActionBar: FakeBulkActionBar,
      api,
      ...(extraGlobals || {}),
    },
  );
  return { ...env, captured, apiCalls, api };
}

test("mountOrdersBulkBar returns null when table is null", () => {
  const { sandbox, captured } = setupWiring();
  const result = sandbox.mountOrdersBulkBar(null);
  assert.equal(result, null);
  assert.equal(captured.args, null);
});

test("mountOrdersBulkBar returns null when table is undefined", () => {
  const { sandbox, captured } = setupWiring();
  const result = sandbox.mountOrdersBulkBar(undefined);
  assert.equal(result, null);
  assert.equal(captured.args, null);
});

test("mountOrdersBulkBar registers exactly 1 action with id 'status'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  const ids = captured.args.actions.map(a => a.id);
  assert.deepEqual(plain(ids), ["status"]);
});

test("status action uses unified confirm:'modal' and exposes customControls", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  const action = captured.args.actions.find(a => a.id === "status");
  assert.equal(action.confirm, "modal");
  assert.equal(action.icon, "arrow-right-circle");
  assert.equal(typeof action.label, "string");
  assert.equal(typeof action.customControls, "function");
  assert.equal(typeof action.explain, "function");
});

test("getRowName returns 'Заказ #<id>'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  assert.equal(captured.args.getRowName({ id: 42 }), "Заказ #42");
});

test("handler POSTs to /admin/orders/bulk/status with payload as-is", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  const action = captured.args.actions.find(a => a.id === "status");
  // The status value is merged into payload by BulkActionBar from
  // customControls.getValue() — here we pass it explicitly.
  const payload = { target: { kind: "ids", ids: [10, 20] }, status: "processing" };
  await action.handler(payload);
  assert.equal(apiCalls.length, 1);
  assert.equal(apiCalls[0].url, "/admin/orders/bulk/status");
  assert.equal(apiCalls[0].body.status, "processing");
});

test("handler returns {cancelled:true} when api.post returns {_failed:true}", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  apiCalls.__nextResult = { _failed: true, error: "boom" };
  const action = captured.args.actions.find(a => a.id === "status");
  const result = await action.handler({ target: { kind: "ids", ids: [5] }, status: "done" });
  assert.deepEqual(plain(result), { cancelled: true });
});

test("payload target envelope is passed through unchanged", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  const action = captured.args.actions.find(a => a.id === "status");
  const payload = { target: { kind: "ids", ids: [1, 2] }, status: "new" };
  await action.handler(payload);
  assert.deepEqual(plain(apiCalls[0].body.target), { kind: "ids", ids: [1, 2] });
});
