import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

function loadPrototype() {
  const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
  const source = html.match(/<script id="device-trust-model">([\s\S]*?)<\/script>/)?.[1];
  if (!source) throw new Error("Missing device trust model script.");
  const context = {};
  vm.runInNewContext(`${source}\nthis.prototypeApi = { createState, apply };`, context);
  return context.prototypeApi;
}

test("first sight of a peer creates a TOFU trust record", () => {
  const { createState, apply } = loadPrototype();

  const result = apply(createState(), {
    type: "proof",
    agentId: "agent-xiaoming",
    fingerprint: "key-a",
  });

  assert.equal(result.decision, "trusted_first_use");
  assert.equal(JSON.stringify(result.state.trustRecords), JSON.stringify({
    "agent-xiaoming": { fingerprint: "key-a", capability: "recommend" },
  }));
});

test("a known peer with the same fingerprint is accepted as continuous", () => {
  const { createState, apply } = loadPrototype();
  const first = apply(createState(), {
    type: "proof", agentId: "agent-xiaoming", fingerprint: "key-a",
  });

  const reconnect = apply(first.state, {
    type: "proof", agentId: "agent-xiaoming", fingerprint: "key-a",
  });

  assert.equal(reconnect.decision, "trusted_existing");
  assert.equal(reconnect.state.trustRecords["agent-xiaoming"].fingerprint, "key-a");
});

test("a changed fingerprint for a known agent is rejected without replacing trust", () => {
  const { createState, apply } = loadPrototype();
  const first = apply(createState(), {
    type: "proof", agentId: "agent-xiaoming", fingerprint: "key-a",
  });

  const changed = apply(first.state, {
    type: "proof", agentId: "agent-xiaoming", fingerprint: "key-b",
  });

  assert.equal(changed.decision, "rejected_key_changed");
  assert.equal(changed.state.trustRecords["agent-xiaoming"].fingerprint, "key-a");
});

test("after revocation, the next proof becomes a new first-use trust", () => {
  const { createState, apply } = loadPrototype();
  const first = apply(createState(), {
    type: "proof", agentId: "agent-xiaoming", fingerprint: "key-a",
  });
  const revoked = apply(first.state, { type: "revoke", agentId: "agent-xiaoming" });
  const reintroduced = apply(revoked.state, {
    type: "proof", agentId: "agent-xiaoming", fingerprint: "key-b",
  });

  assert.equal(revoked.decision, "revoked");
  assert.equal(reintroduced.decision, "trusted_first_use");
  assert.equal(reintroduced.state.trustRecords["agent-xiaoming"].fingerprint, "key-b");
});
