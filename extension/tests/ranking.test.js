// Analise de Ranking (secao 16): modelo do pedido, tarefa vinda do app e o caminho no service worker.
const test = require("node:test");
const assert = require("node:assert/strict");
const { isPointTemplate, pointUrl, cleanTask, createRankingRegistry } = require("../src/lib/ranking.js");
const { createRouter, rankingBegin, rankingRun } = require("../src/lib/run.js");
const ranking = require("../src/lib/ranking.js");

// Modelo como o <link> de preload da busca do Maps (2026-10-11), encurtado no fim.
const TEMPLATE = "https://www.google.com/search?tbm=map&authuser=0&hl=pt-BR&gl=br&q=oftalmologista&pb=%211softalmologista" +
  "%214m8%211m3%211d30007.744165240776%212d-43.9123456%213d-19.9123456%213m2%211i1024%212i768%214f13.1%217i20%2110b1";
const TASK = { id: 5, keyword: "oftalmologista", view: 1000, points: [[-19.95, -43.95], [-19.92, -43.92]],
               searchUrl: "https://www.google.com/maps/search/oftalmologista/@-19.9123456,-43.9123456,15z?hl=pt-BR" };

test("modelo: so a busca tbm=map do proprio Google, com o trecho do ponto de vista", () => {
  assert.ok(isPointTemplate(TEMPLATE));
  assert.ok(!isPointTemplate(TEMPLATE.replace("https://www.google.com", "https://evil.example")));
  assert.ok(!isPointTemplate(TEMPLATE.replace("tbm=map", "tbm=isch")));
  assert.ok(!isPointTemplate(TEMPLATE.replace("%211d30007.744165240776", "")));
  assert.ok(!isPointTemplate(null));
});

test("ponto: troca so distancia e coordenadas (lng em !2d, lat em !3d)", () => {
  const url = pointUrl(TEMPLATE, -21.1, -42.9, 1000);
  assert.ok(url.includes("%211d1000%212d-42.9000000%213d-21.1000000%213m2"));
  assert.equal(url.replace(/%211d[^%]+%212d[^%]+%213d[^%]+/, ""), TEMPLATE.replace(/%211d[^%]+%212d[^%]+%213d[^%]+/, ""));
  assert.equal(pointUrl(TEMPLATE, 91, 0, 1000), null);
  assert.equal(pointUrl(TEMPLATE, 0, 0, 50), null);
  assert.equal(pointUrl("https://evil.example/?%211d1%212d1%213d1", 0, 0, 1000), null);
});

test("tarefa do app: so o formato esperado", () => {
  assert.deepEqual(cleanTask(TASK), TASK);
  assert.equal(cleanTask({ ...TASK, id: "5" }), null);
  assert.equal(cleanTask({ ...TASK, points: [] }), null);
  assert.equal(cleanTask({ ...TASK, points: Array(225).fill([0, 0]) }).points.length, 225); // 15x15
  assert.equal(cleanTask({ ...TASK, points: Array(226).fill([0, 0]) }), null);
  assert.equal(cleanTask({ ...TASK, points: [[0, 200]] }), null);
  assert.equal(cleanTask({ ...TASK, searchUrl: "https://evil.example/maps/search/x" }), null);
  assert.equal(cleanTask({ ...TASK, keyword: "x".repeat(81) }), null);
  assert.equal(cleanTask({ ...TASK, view: 1e6 }), null);
  assert.equal(cleanTask([]), null);
});

test("registro: papel da aba, sinal de vida e desistencia", () => {
  const timers = [];
  let expired = null;
  const reg = createRankingRegistry({ setTimer: (fn) => { timers.push(fn); return timers.length; }, clearTimer: () => {},
                                       onTimeout: (t) => { expired = t; } });
  assert.equal(reg.role(1), null);
  reg.register(1, TASK);
  assert.equal(reg.role(1).kind, "ranking");
  assert.deepEqual(reg.role(1).points, TASK.points);
  timers[timers.length - 1]();
  assert.equal(expired.task, TASK);
  assert.equal(reg.role(1), null);
  reg.register(2, TASK);
  assert.equal(reg.remove(2).task, TASK);
  assert.equal(reg.remove(2), null);
  reg.opened(3, 5, 40); // aba aberta pela extensao (clique no app): primeiro le o perfil
  assert.deepEqual(reg.role(3), { kind: "ranking-center", id: 5 });
  assert.equal(reg.task(3), null);
  reg.register(3, TASK);
  assert.equal(reg.role(3).kind, "ranking");
  assert.equal(reg.entry(3).appTabId, 40);
});

function fakeApp(responses) {
  const calls = [];
  const fn = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body), options });
    const r = responses.shift();
    return { status: r.status, json: async () => r.body };
  };
  fn.calls = calls;
  return fn;
}

function router(fetchFn, tabs = [], rankings = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} }), events = []) {
  const route = createRouter({ extensionId: "ext", optionsUrl: "chrome-extension://ext/options.html", arming: {},
    getSecret: async () => "s".repeat(40), fetchFn, createTab: async (url) => { tabs.push(url); return { id: 99 }; },
    mapsUrl: () => null, urls: {}, runner: { role: () => null, opening: () => false }, rankings, ranking,
    closeTab: async (id) => events.push(["close", id]), focusTab: async (id) => events.push(["focus", id]) });
  return { route, rankings };
}
const MAPS = { id: "ext", url: "https://www.google.com/maps/place/x", tab: { id: 7 } };
const SEARCH = { id: "ext", url: "https://www.google.com/maps/search/oftalmologista/@-19,-43,15z", tab: { id: 7 } };

test("service worker: inicio, pontos e fim vao so para o app, com o segredo", async () => {
  const fetchFn = fakeApp([{ status: 200, body: { ok: true, task: TASK } },
                           { status: 200, body: { ok: true, received: 1, total: 2 } },
                           { status: 200, body: { ok: true, status: "pronta" } }]);
  const tabs = [];
  const { route } = router(fetchFn, tabs);
  const begin = await route({ type: "seals:ranking-begin", place: ")]}'\n[]" }, MAPS);
  assert.deepEqual(begin, { ok: true, url: TASK.searchUrl, points: 2 });
  assert.equal((await route({ type: "seals:role?" }, SEARCH)).role.kind, "ranking");
  assert.equal((await route({ type: "seals:ranking-point", i: 0, text: "x" }, SEARCH)).ok, true);
  assert.equal((await route({ type: "seals:ranking-point", i: 5, text: "x" }, SEARCH)).ok, false); // fora da grade
  assert.equal((await route({ type: "seals:ranking-end", cancelled: false, error: null }, SEARCH)).ok, true);
  assert.deepEqual(fetchFn.calls.map((c) => c.url), ["http://127.0.0.1:8000/ranking/inicio",
    "http://127.0.0.1:8000/ranking/ponto", "http://127.0.0.1:8000/ranking/fim"]);
  for (const c of fetchFn.calls) {
    assert.equal(c.options.headers["X-Seals-Secret"], "s".repeat(40));
    assert.equal(c.options.credentials, "omit");
  }
  assert.deepEqual(fetchFn.calls[1].body, { id: 5, i: 0, text: "x" });
  assert.deepEqual(tabs, ["http://127.0.0.1:8000/ranking/analise?id=5"]);
  assert.equal((await route({ type: "seals:role?" }, SEARCH)).role, null); // a aba deixa de ter papel
});

test("service worker: sem analise preparada, o erro do app chega a faixa e nada fica registrado", async () => {
  const fetchFn = fakeApp([{ status: 409, body: { ok: false, error: "não há análise de ranking esperando" } }]);
  const { route, rankings } = router(fetchFn);
  const r = await route({ type: "seals:ranking-begin", place: "x" }, MAPS);
  assert.deepEqual(r, { ok: false, error: "não há análise de ranking esperando" });
  assert.equal(rankings.role(7), null);
  assert.equal((await route({ type: "seals:ranking-point", i: 0, text: "x" }, SEARCH)).ok, false);
});

test("service worker: tarefa estranha do app e recusada; pedidos de fora do Maps sao ignorados", async () => {
  const fetchFn = fakeApp([{ status: 200, body: { ok: true, task: { ...TASK, searchUrl: "https://evil.example/" } } }]);
  const { route } = router(fetchFn);
  assert.deepEqual(await route({ type: "seals:ranking-begin", place: "x" }, MAPS), { ok: false, error: "tarefa inesperada do app" });
  assert.equal(route({ type: "seals:ranking-begin", place: "x" }, { ...MAPS, url: "https://evil.example/" }), null);
  assert.equal(route({ type: "seals:ranking-point", i: 0, text: "x" }, { ...MAPS, id: "outra" }), null);
  assert.deepEqual(await rankingBegin({ place: "", tabId: 1, rankings: null, ranking, getSecret: async () => "s", fetchFn }),
    { ok: false, error: "os dados do perfil ainda não chegaram. Espere a página carregar e clique de novo." });
});

const APP_PAGE = { url: "http://127.0.0.1:8000/ranking/analise?id=5", tab: { id: 40 } };
const PING_OK = { status: 204, body: null };

test("clique no app: so de 127.0.0.1:8000; o app diz qual perfil abrir; no fim volta para a aba do app", async () => {
  const fetchFn = fakeApp([PING_OK, { status: 200, body: { ok: true, id: 5, mapsUrl: "https://www.google.com/maps?cid=123&hl=pt-BR" } },
                           { status: 200, body: { ok: true, task: TASK } },
                           { status: 200, body: { ok: true, status: "pronta" } }]);
  const rankings = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} });
  const opened = [];
  const r = await rankingRun({ msg: { type: "seals:ranking-run", id: 5 }, sender: APP_PAGE, rankings, ranking,
    getSecret: async () => "s".repeat(40), fetchFn, openTab: async (url) => { opened.push(url); return { id: 7 }; } });
  assert.deepEqual(r, { ok: true });
  assert.deepEqual(opened, ["https://www.google.com/maps?cid=123&hl=pt-BR"]);
  assert.deepEqual(fetchFn.calls[1].body, { id: 5 });
  const tabs = [], events = [];
  const { route } = router(fetchFn, tabs, rankings, events);
  assert.deepEqual((await route({ type: "seals:role?" }, MAPS)).role, { kind: "ranking-center", id: 5 });
  assert.equal((await route({ type: "seals:ranking-begin", place: "x" }, MAPS)).ok, true);
  assert.deepEqual(fetchFn.calls[2].body, { place: "x", id: 5 }); // a mesma analise que a extensao abriu
  assert.equal((await route({ type: "seals:ranking-end", cancelled: false, error: null }, SEARCH)).ok, true);
  assert.deepEqual(events, [["focus", 40], ["close", 7]]);
  assert.deepEqual(tabs, []); // nao abre outra aba: a tela do app se atualiza
});

test("clique no app: outra origem, numero estranho ou endereco estranho do app nao abrem nada", async () => {
  const rankings = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} });
  const base = { rankings, ranking, getSecret: async () => "s".repeat(40), openTab: async () => assert.fail("abriu aba") };
  for (const sender of [{ url: "https://evil.example/", tab: { id: 1 } }, { url: "http://127.0.0.1:8001/x", tab: { id: 1 } },
                        { url: "http://127.0.0.1:8000.evil.example/", tab: { id: 1 } }, { url: "http://127.0.0.1:8000/x" }]) {
    assert.equal(await rankingRun({ ...base, msg: { id: 5 }, sender, fetchFn: fakeApp([]) }), null, sender.url);
  }
  assert.equal((await rankingRun({ ...base, msg: { id: "5" }, sender: APP_PAGE, fetchFn: fakeApp([]) })).ok, false);
  const fetchFn = fakeApp([PING_OK, { status: 200, body: { ok: true, id: 5, mapsUrl: "https://evil.example/maps?cid=1&hl=pt-BR" } }]);
  assert.deepEqual(await rankingRun({ ...base, msg: { id: 5 }, sender: APP_PAGE, fetchFn }), { ok: false, error: "resposta inesperada do app" });
});

test("aba aberta pela extensao: perfil errado avisa o app (a tela mostra o motivo)", async () => {
  const fetchFn = fakeApp([{ status: 409, body: { ok: false, error: "o perfil aberto no Maps não é o do cliente desta análise." } },
                           { status: 200, body: { ok: true, status: "erro" } }]);
  const rankings = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} });
  rankings.opened(7, 5, 40);
  const { route } = router(fetchFn, [], rankings);
  const r = await route({ type: "seals:ranking-begin", place: "x" }, MAPS);
  assert.equal(r.ok, false);
  assert.equal(fetchFn.calls[1].url, "http://127.0.0.1:8000/ranking/fim");
  assert.deepEqual(fetchFn.calls[1].body, { id: 5, cancelled: false, error: "o perfil aberto no Maps não é o do cliente desta análise." });
  assert.equal(rankings.role(7), null);
});

test("varias palavras-chave: o fim de uma ja traz a proxima, na mesma aba; so no fim volta para o app", async () => {
  const NEXT = { ...TASK, id: 6, keyword: "ortodontista", searchUrl: "https://www.google.com/maps/search/ortodontista/@-19.9,-43.9,15z?hl=pt-BR" };
  const fetchFn = fakeApp([{ status: 200, body: { ok: true, status: "pronta", next: NEXT } },
                           { status: 200, body: { ok: true, status: "pronta", next: null } }]);
  const rankings = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} });
  rankings.opened(7, 5, 40);
  rankings.register(7, TASK);
  const tabs = [], events = [];
  const { route } = router(fetchFn, tabs, rankings, events);
  const first = await route({ type: "seals:ranking-end", cancelled: false, error: null }, SEARCH);
  assert.deepEqual(first, { ok: true, status: "pronta", next: NEXT.searchUrl, keyword: "ortodontista", points: 2 });
  assert.equal(rankings.role(7).id, 6);
  assert.equal(rankings.entry(7).appTabId, 40); // a aba do app continua guardada
  assert.deepEqual(events, []);
  const last = await route({ type: "seals:ranking-end", cancelled: false, error: null }, SEARCH);
  assert.equal(last.ok, true);
  assert.equal(last.next, undefined);
  assert.deepEqual(events, [["focus", 40], ["close", 7]]);
  // proxima com formato estranho: nao segue
  const bad = fakeApp([{ status: 200, body: { ok: true, status: "pronta", next: { ...NEXT, searchUrl: "https://evil.example/" } } }]);
  const r2 = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} });
  r2.register(7, TASK);
  const res = await router(bad, [], r2).route({ type: "seals:ranking-end", cancelled: false, error: null }, SEARCH);
  assert.equal(res.next, undefined);
  assert.equal(r2.role(7), null);
});
