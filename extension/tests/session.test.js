const test = require("node:test");
const assert = require("node:assert/strict");
const { classify } = require("../src/lib/match.js");
const { CaptureBuffer } = require("../src/lib/buffer.js");
const { runSteps } = require("../src/lib/steps.js");
const { createSession, CAPTURE_KEYS } = require("../src/lib/session.js");

const WIN = {};
const PLACE_URL = "https://www.google.com/maps/preview/place?pb=1";
const msg = (kind, url, text, source = WIN) => ({ source, data: { __seals: 1, kind, url, text } });

function setup({ check = () => null, steps } = {}) {
  const buffer = new CaptureBuffer();
  const sent = [];
  const session = createSession({
    buffer, classify, runSteps,
    submit: async (capture) => { sent.push(capture); return { ok: true, id: 1 }; },
    buildSteps: (b) => ({
      check,
      steps: steps || [{ key: "place", label: "perfil", run: async () => b.latest("place") }],
    }),
    now: () => new Date("2026-10-09T12:00:00Z"),
  });
  return { buffer, sent, session };
}

test("captura passiva so enche o buffer da pagina: nada e enviado sem o clique", async () => {
  const { buffer, sent, session } = setup();
  for (let i = 0; i < 50; i++) session.onHookMessage(msg("place", PLACE_URL, `p${i}`), WIN);
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(buffer.entries.length, 50);
  assert.equal(sent.length, 0);
});

test("so depois do start (clique) a captura e entregue, uma vez, com as chaves esperadas", async () => {
  const { sent, session } = setup();
  session.onHookMessage(msg("place", PLACE_URL, "dados"), WIN);
  const res = await session.start({ sleep: async () => {} });
  assert.equal(res.ok, true);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].place, "dados");
  assert.equal(sent[0].capturedAt, "2026-10-09T12:00:00.000Z");
  for (const key of CAPTURE_KEYS) assert.ok(key in sent[0], key);
  assert.equal(sent[0].reviews, null); // fonte sem passo = nao coletada
});

test("mensagens de outra janela, sem marca ou com tipo que nao bate com a URL sao ignoradas", () => {
  const { buffer, session } = setup();
  assert.equal(session.onHookMessage(msg("place", PLACE_URL, "x", {}), WIN), false);
  assert.equal(session.onHookMessage({ source: WIN, data: { kind: "place", url: PLACE_URL, text: "x" } }, WIN), false);
  assert.equal(session.onHookMessage(msg("reviews", PLACE_URL, "x"), WIN), false);
  assert.equal(session.onHookMessage(msg("place", "https://evil.example/maps/preview/place", "x"), WIN), false);
  assert.equal(buffer.entries.length, 0);
});

test("checagem que falha nao envia nada", async () => {
  const { sent, session } = setup({ check: () => "Maps fora do português" });
  const res = await session.start({ sleep: async () => {} });
  assert.deepEqual(res, { ok: false, reason: "Maps fora do português" });
  assert.equal(sent.length, 0);
});

test("cancelada nao envia; segunda captura simultanea e recusada", async () => {
  const { sent, session } = setup({ steps: [{ key: "place", label: "", run: async () => "x" }, { key: "search", label: "", run: async () => [] }] });
  const res = await session.start({ sleep: async () => {}, isCancelled: () => true });
  assert.equal(res.reason, "cancelled");
  assert.equal(sent.length, 0);

  let release;
  const slow = setup({ steps: [{ key: "place", label: "", run: () => new Promise((r) => { release = r; }) }] });
  const first = slow.session.start({ sleep: async () => {} });
  assert.deepEqual(await slow.session.start({ sleep: async () => {} }), { ok: false, reason: "busy" });
  release("x");
  await first;
  assert.equal(slow.sent.length, 1);
});
