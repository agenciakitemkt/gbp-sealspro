const test = require("node:test");
const assert = require("node:assert/strict");
const { classify } = require("../src/lib/match.js");
const { installHook, MAX_TEXT } = require("../src/lib/hook.js");

function fakeWindow(bodies) {
  const calls = [];
  class FakeXHR {
    constructor() { this.listeners = {}; this.responseType = ""; }
    open(method, url) { this.url = url; }
    send() {
      if (this.stayOpen) return; // simula pedido que fica aberto (entrega em partes)
      this.responseText = bodies[this.url] || "";
      this.readyState = 4;
      for (const name of this.order || ["load"]) (this.listeners[name] || []).forEach((f) => f());
    }
    addEventListener(name, f) { (this.listeners[name] = this.listeners[name] || []).push(f); }
  }
  return {
    location: { href: "https://www.google.com/maps/place/x" },
    fetch: async (url) => { calls.push(url); return new Response(bodies[url] || "x"); },
    XMLHttpRequest: FakeXHR,
    calls,
  };
}

const PLACE = "https://www.google.com/maps/preview/place?pb=1";
const OTHER = "https://www.google.com/maps/vt?pb=2";
const REVIEWS = "https://www.google.com/maps/_/MapsWizUi/data/batchexecute?rpcids=qv9Egd";

test("fetch: copia so as respostas reconhecidas e devolve a resposta original intacta", async () => {
  const win = fakeWindow({ [PLACE]: ")]}'\n[1]", [OTHER]: "nao" });
  const got = [];
  installHook(win, classify, (m) => got.push(m));
  const r1 = await win.fetch(PLACE);
  const r2 = await win.fetch(OTHER);
  assert.equal(await r1.text(), ")]}'\n[1]");
  assert.equal(await r2.text(), "nao");
  await new Promise((r) => setTimeout(r, 10));
  assert.deepEqual(got.map((m) => m.kind), ["place"]);
  assert.equal(got[0].text, ")]}'\n[1]");
  assert.deepEqual(win.calls, [PLACE, OTHER]);
});

test("XHR: copia a resposta reconhecida", () => {
  const win = fakeWindow({ [REVIEWS]: "pagina" });
  const got = [];
  installHook(win, classify, (m) => got.push(m));
  const x = new win.XMLHttpRequest();
  x.open("POST", REVIEWS);
  x.send();
  const y = new win.XMLHttpRequest();
  y.open("GET", OTHER);
  y.send();
  assert.deepEqual(got, [{ kind: "reviews", url: REVIEWS, text: "pagina" }]);
});

test("resposta grande demais e ignorada; instalar duas vezes nao duplica", async () => {
  const win = fakeWindow({ [PLACE]: "x".repeat(MAX_TEXT + 1) });
  const got = [];
  assert.equal(installHook(win, classify, (m) => got.push(m)), true);
  assert.equal(installHook(win, classify, (m) => got.push(m)), false);
  await win.fetch(PLACE);
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(got.length, 0);
});

test("rastro de diagnostico: so caminho e rpcids, nunca outros parametros", () => {
  const { traceOf } = require("../src/lib/hook.js");
  assert.equal(traceOf("https://www.google.com/maps/_/MapsWizUi/data/batchexecute?rpcids=hspqX&f.sid=123&bl=x", "https://www.google.com/"),
    "/maps/_/MapsWizUi/data/batchexecute?rpcids=hspqX");
  assert.equal(traceOf("https://www.google.com/search?tbm=map&q=nome+do+cliente&pb=!1m2", "https://www.google.com/"), "/search?tbm=map");
  assert.equal(traceOf("https://www.google.com/maps/preview/place?pb=!1s0x1:0x2&q=x", "https://www.google.com/"), "/maps/preview/place");
  assert.equal(traceOf("https://evil.example/x?rpcids=a", "https://www.google.com/"), null);
});

test("rastro chega pela funcao trace, para todo pedido ao Google", async () => {
  const win = fakeWindow({});
  const traced = [];
  installHook(win, classify, () => {}, (t) => traced.push(t));
  await win.fetch("https://www.google.com/maps/vt?pb=1&x=2");
  await win.fetch(PLACE);
  await new Promise((r) => setTimeout(r, 10));
  assert.deepEqual(traced, ["/maps/vt [fetch]", "/maps/preview/place [fetch]", "<= place fetch: 1 caracteres"]);
});

test("XHR que termina so por readystatechange tambem e entregue, uma vez", () => {
  const win = fakeWindow({ [REVIEWS]: "pagina" });
  const got = [];
  installHook(win, classify, (m) => got.push(m));
  const x = new win.XMLHttpRequest();
  x.order = ["readystatechange", "load", "loadend"];
  x.open("POST", REVIEWS);
  x.send();
  const y = new win.XMLHttpRequest();
  y.order = ["readystatechange"]; // sem load
  y.open("POST", REVIEWS);
  y.send();
  assert.equal(got.length, 2);
});

test("busca em partes: entrega quando o texto ja recebido e um JSON completo, sem o pedido fechar", () => {
  const SEARCH = "https://www.google.com/search?tbm=map&pb=1";
  const win = fakeWindow({});
  const got = [];
  installHook(win, classify, (m) => got.push(m));
  const x = new win.XMLHttpRequest();
  x.stayOpen = true; // o pedido nao conclui sozinho
  x.open("GET", SEARCH);
  x.send();
  const fire = (name) => (x.listeners[name] || []).forEach((f) => f());
  x.readyState = 3; x.responseText = ")]}'\n[[1,2],[3"; fire("readystatechange");
  assert.equal(got.length, 0); // ainda incompleto
  x.responseText = ")]}'\n[[1,2],[3]]"; fire("progress");
  assert.equal(got.length, 1);
  assert.equal(got[0].kind, "search");
  x.readyState = 4; fire("readystatechange"); fire("load"); fire("loadend");
  assert.equal(got.length, 1); // uma vez so
});

test("so a busca e entregue parcial; avaliacoes esperam o fim do pedido", () => {
  const win = fakeWindow({});
  const got = [];
  installHook(win, classify, (m) => got.push(m));
  const x = new win.XMLHttpRequest();
  x.stayOpen = true;
  x.open("POST", REVIEWS);
  x.send();
  x.readyState = 3; x.responseText = "[1]";
  (x.listeners.progress || []).forEach((f) => f());
  assert.equal(got.length, 0);
});
