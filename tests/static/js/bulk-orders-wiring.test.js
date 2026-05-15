"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const { loadBrowserScripts } = require("./_harness");

// vm contexts have their own Array prototype; assert.deepEqual rejects
// cross-context objects. Normalize via JSON round-trip.
const plain = (x) => JSON.parse(JSON.stringify(x));

// NOTE: loadBrowserScripts applies extraGlobals BEFORE running scripts
// (Object.assign before the for-loop), so the IIFE will overwrite any
// injected bulkPickOrderStatus. Override sandbox.bulkPickOrderStatus
// AFTER loadBrowserScripts returns for per-test picker control.

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
    ["static/js/bulk-orders-wiring.js"],
    {
      BulkActionBar: FakeBulkActionBar,
      api,
      bulkFmtNumber: (n) => String(n),
      ...(extraGlobals || {}),
    },
  );
  return { ...env, captured, apiCalls, api };
}

// ── 1. null guard ────────────────────────────────────────────────────────────

test("mountOrdersBulkBar returns null when table is null", () => {
  const { sandbox, captured } = setupWiring();
  const result = sandbox.mountOrdersBulkBar(null);
  assert.equal(result, null);
  assert.equal(captured.args, null);
});

// ── 2. undefined guard ───────────────────────────────────────────────────────

test("mountOrdersBulkBar returns null when table is undefined", () => {
  const { sandbox, captured } = setupWiring();
  const result = sandbox.mountOrdersBulkBar(undefined);
  assert.equal(result, null);
  assert.equal(captured.args, null);
});

// ── 3. exactly 1 action with id "status" ─────────────────────────────────────

test("mountOrdersBulkBar registers exactly 1 action with id 'status'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  const ids = captured.args.actions.map(a => a.id);
  assert.deepEqual(plain(ids), ["status"]);
});

// ── 4. action metadata ───────────────────────────────────────────────────────

test("status action has confirm 'none', icon 'arrow-right-circle', label 'Изменить статус'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  const action = captured.args.actions.find(a => a.id === "status");
  assert.equal(action.confirm, "none");
  assert.equal(action.icon, "arrow-right-circle");
  assert.equal(action.label, "Изменить статус");
});

// ── 5. getRowName ─────────────────────────────────────────────────────────────

test("getRowName returns 'Заказ #<id>'", () => {
  const { sandbox, captured } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  assert.equal(captured.args.getRowName({ id: 42 }), "Заказ #42");
});

// ── 6. handler POSTs with picked status ──────────────────────────────────────

test("handler POSTs to /admin/orders/bulk/status with picked status merged into payload", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  // Override picker AFTER script load (IIFE wrote its own version first).
  sandbox.bulkPickOrderStatus = async () => "processing";
  const action = captured.args.actions.find(a => a.id === "status");
  const payload = { target: { kind: "ids", ids: [10, 20] } };
  await action.handler(payload);
  assert.equal(apiCalls.length, 1);
  assert.equal(apiCalls[0].url, "/admin/orders/bulk/status");
  assert.equal(apiCalls[0].body.status, "processing");
});

// ── 7. handler returns {cancelled:true} when picker resolves to null ─────────

test("handler returns {cancelled:true} and does NOT call api.post when picker returns null", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  sandbox.bulkPickOrderStatus = async () => null;
  const action = captured.args.actions.find(a => a.id === "status");
  const result = await action.handler({ target: { kind: "ids", ids: [1] } });
  assert.deepEqual(plain(result), { cancelled: true });
  assert.equal(apiCalls.length, 0);
});

// ── 8. handler returns {cancelled:true} when api.post returns {_failed:true} ─

test("handler returns {cancelled:true} when api.post returns {_failed:true}", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  sandbox.bulkPickOrderStatus = async () => "done";
  apiCalls.__nextResult = { _failed: true, error: "boom" };
  const action = captured.args.actions.find(a => a.id === "status");
  const result = await action.handler({ target: { kind: "ids", ids: [5] } });
  assert.deepEqual(plain(result), { cancelled: true });
});

// ── 9. payload target envelope is passed through unchanged ───────────────────

test("handler passes target envelope unchanged into POST body", async () => {
  const { sandbox, captured, apiCalls } = setupWiring();
  sandbox.mountOrdersBulkBar({});
  sandbox.bulkPickOrderStatus = async () => "new";
  const action = captured.args.actions.find(a => a.id === "status");
  const payload = { target: { kind: "ids", ids: [1, 2] } };
  await action.handler(payload);
  assert.deepEqual(plain(apiCalls[0].body.target), { kind: "ids", ids: [1, 2] });
});

// ── 10. window.bulkPickOrderStatus export exists after module load ────────────

test("window.bulkPickOrderStatus is set to a function by the module (production export)", () => {
  // Load WITHOUT injecting a stub so we see what the IIFE itself exports.
  const { sandbox } = loadBrowserScripts(
    ["static/js/bulk-orders-wiring.js"],
    {
      BulkActionBar: class { constructor() {} },
      api: { post: async () => ({}), get: async () => ({}) },
      bulkFmtNumber: (n) => String(n),
    },
  );
  assert.equal(typeof sandbox.bulkPickOrderStatus, "function");
});
