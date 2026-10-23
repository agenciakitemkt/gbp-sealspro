const test = require("node:test");
const assert = require("node:assert/strict");
const { guardTrusted } = require("../src/lib/button.js");

test("so clique de verdade (isTrusted) inicia", () => {
  let calls = 0;
  const onClick = guardTrusted(() => { calls += 1; });
  assert.equal(onClick({ isTrusted: false }), false);
  assert.equal(onClick({}), false);
  assert.equal(onClick(new Event("click")), false); // evento criado por script: isTrusted = false
  assert.equal(onClick(null), false);
  assert.equal(calls, 0);
  assert.equal(onClick({ isTrusted: true, preventDefault() {}, stopPropagation() {} }), true);
  assert.equal(calls, 1);
});
