// Minimal sandbox to load browser-shaped JS files under node:test.
// We avoid heavy DOM (jsdom) — the modules under test are pure data plus
// a class that we can drive by seeding fields directly.

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..", "..", "..");

function makeSessionStorage() {
  const store = new Map();
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => { store.set(k, String(v)); },
    removeItem: (k) => { store.delete(k); },
    clear: () => { store.clear(); },
    _store: store,
  };
}

function makeContainerEl() {
  return {
    innerHTML: "",
    querySelectorAll: () => [],
    querySelector: () => null,
  };
}

function makeDocument(container) {
  const listeners = { click: [], keydown: [] };
  return {
    getElementById: (id) => (id ? container : null),
    addEventListener: (type, fn) => { (listeners[type] ||= []).push(fn); },
    removeEventListener: (type, fn) => {
      const arr = listeners[type];
      if (!arr) return;
      const i = arr.indexOf(fn);
      if (i >= 0) arr.splice(i, 1);
    },
    body: {
      _events: [],
      dispatchEvent(e) { this._events.push({ type: e.type, detail: e.detail }); return true; },
    },
    _listeners: listeners,
  };
}

function loadBrowserScripts(files, extraGlobals) {
  const container = makeContainerEl();
  const doc = makeDocument(container);
  const sandbox = {
    window: undefined,
    document: doc,
    sessionStorage: makeSessionStorage(),
    console,
    setTimeout, clearTimeout,
    URLSearchParams, // smart-table.load uses it but we don't invoke load()
    CustomEvent: function (type, init) { return { type, detail: init && init.detail }; },
    Set, Map,
    // smart-table.js depends on `esc` from utils.js.
    esc: (v) => String(v == null ? "" : v)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;"),
    api: { get: async () => ({}) },
  };
  sandbox.window = sandbox;             // window === globalThis in our shim
  sandbox.globalThis = sandbox;
  Object.assign(sandbox, extraGlobals || {});
  vm.createContext(sandbox);

  for (const rel of files) {
    const full = path.join(ROOT, rel);
    const src = fs.readFileSync(full, "utf8");
    vm.runInContext(src, sandbox, { filename: rel });
  }
  return { sandbox, doc, container };
}

module.exports = {
  loadBrowserScripts,
  makeContainerEl,
  makeDocument,
  makeSessionStorage,
  ROOT,
};
