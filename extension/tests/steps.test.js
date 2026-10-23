const test = require("node:test");
const assert = require("node:assert/strict");
const { runSteps, pauseMs, PAUSE_MIN, PAUSE_MAX } = require("../src/lib/steps.js");

test("pausa entre 2 e 5 segundos", () => {
  assert.equal(pauseMs(() => 0), PAUSE_MIN);
  assert.equal(pauseMs(() => 0.999999), PAUSE_MAX);
  for (let i = 0; i < 200; i++) {
    const p = pauseMs(Math.random);
    assert.ok(p >= 2000 && p <= 5000, p);
  }
});

test("roda um passo de cada vez, em ordem, com pausa entre eles", async () => {
  const log = [];
  const sleeps = [];
  const steps = ["a", "b", "c"].map((k) => ({ key: k, label: k, run: async () => { log.push(k); return k.toUpperCase(); } }));
  const out = await runSteps(steps, { sleep: async (ms) => { sleeps.push(ms); log.push("pausa"); }, random: () => 0.5 });
  assert.deepEqual(log, ["a", "pausa", "b", "pausa", "c"]);
  assert.deepEqual(out.results, { a: "A", b: "B", c: "C" });
  assert.ok(sleeps.every((ms) => ms >= 2000 && ms <= 5000));
});

test("passo que falha devolve null e os outros continuam", async () => {
  const steps = [
    { key: "reviews", label: "", run: async () => { throw new Error("aba nao encontrada"); } },
    { key: "search", label: "", run: async () => ["ok"] },
  ];
  const out = await runSteps(steps, { sleep: async () => {} });
  assert.deepEqual(out.results, { reviews: null, search: ["ok"] });
  assert.deepEqual(out.errors, [{ key: "reviews", message: "aba nao encontrada" }]);
});

test("cancelar para antes do proximo passo", async () => {
  let cancel = false;
  const ran = [];
  const steps = ["a", "b", "c"].map((k) => ({ key: k, label: k, run: async () => { ran.push(k); if (k === "a") cancel = true; } }));
  const out = await runSteps(steps, { sleep: async () => {}, isCancelled: () => cancel });
  assert.deepEqual(ran, ["a"]);
  assert.equal(out.cancelled, true);
});
