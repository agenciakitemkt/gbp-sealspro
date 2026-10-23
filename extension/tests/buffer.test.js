const test = require("node:test");
const assert = require("node:assert/strict");
const { CaptureBuffer, attachLifecycle } = require("../src/lib/buffer.js");

test("guarda por tipo e em ordem", () => {
  const b = new CaptureBuffer();
  b.add("place", "a");
  const mark = b.seq;
  b.add("reviews", "r1");
  b.add("reviews", "r2");
  b.add("place", "b");
  assert.deepEqual(b.since(mark, "reviews"), ["r1", "r2"]);
  assert.equal(b.latest("place"), "b");
  assert.equal(b.latest("search"), null);
});

test("tipo desconhecido ou texto que nao e string e recusado", () => {
  const b = new CaptureBuffer();
  assert.equal(b.add("cookies", "x"), false);
  assert.equal(b.add("place", { x: 1 }), false);
  assert.equal(b.entries.length, 0);
});

test("limite de tamanho e de quantidade", () => {
  const b = new CaptureBuffer({ maxBytes: 10, maxEntries: 3 });
  assert.equal(b.add("reviews", "12345"), true);
  assert.equal(b.add("reviews", "123456"), false); // passaria de 10 bytes
  assert.equal(b.overflow, true);
  assert.equal(b.bytes, 5);
  const c = new CaptureBuffer({ maxBytes: 1000, maxEntries: 2 });
  c.add("photos", "a"); c.add("photos", "b");
  assert.equal(c.add("photos", "c"), false);
  assert.equal(c.entries.length, 2);
});

test("descartado ao sair da pagina (pagehide e beforeunload)", () => {
  for (const event of ["pagehide", "beforeunload"]) {
    const target = new EventTarget();
    const b = new CaptureBuffer();
    attachLifecycle(target, b);
    b.add("place", "dados");
    target.dispatchEvent(new Event(event));
    assert.equal(b.entries.length, 0, event);
    assert.equal(b.bytes, 0);
    assert.equal(b.latest("place"), null);
  }
});
