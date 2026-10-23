// Busca de Leads (secao 18): pagina de cada pedido, tarefa vinda do app, clique na tela e o caminho no service worker.
const test = require("node:test");
const assert = require("node:assert/strict");
const ranking = require("../src/lib/ranking.js");
const { pointUrl, cleanTask, createRankingRegistry, appPrefix } = ranking;
const { createRouter, leadsRun, rankingTimeout } = require("../src/lib/run.js");

const TEMPLATE = "https://www.google.com/search?tbm=map&authuser=0&hl=pt-BR&gl=br&q=dentista&pb=%211sdentista" +
  "%214m8%211m3%211d60018.0%212d-43.9386%213d-19.9191%213m2%211i1024%212i768%214f13.1%217i20%2110b1";
const TASK = { id: 3, mode: "leads", keyword: "dentista", view: 4000,
               points: [[-19.95, -43.95, 0], [-19.95, -43.95, 20], [-19.92, -43.92, 0]],
               searchUrl: "https://www.google.com/maps/search/dentista/@-19.9100000,-43.9300000,13z?hl=pt-BR" };

test("pagina: !8i<inicio> logo depois de !7i20; so multiplos de 20 ate 100", () => {
  assert.ok(pointUrl(TEMPLATE, -19.9, -43.9, 4000, 40).includes("%217i20%218i40%2110b1"));
  assert.ok(!pointUrl(TEMPLATE, -19.9, -43.9, 4000, 0).includes("%218i"));
  assert.ok(!pointUrl(TEMPLATE, -19.9, -43.9, 4000).includes("%218i")); // ranking: sem pagina
  for (const bad of [10, -20, 120, 1.5, "20"]) assert.equal(pointUrl(TEMPLATE, -19.9, -43.9, 4000, bad), null, String(bad));
  assert.equal(pointUrl(TEMPLATE.replace("%217i20", "%217i10"), -19.9, -43.9, 4000, 20), null);
  assert.equal(pointUrl(TEMPLATE.replace("%217i20", "%217i20%218i20"), -19.9, -43.9, 4000, 20), null);
});

test("tarefa de leads: pontos com a pagina; modo desconhecido ou formato do ranking sao recusados", () => {
  assert.deepEqual(cleanTask(TASK), TASK);
  assert.equal(cleanTask({ ...TASK, mode: "outro" }), null);
  assert.equal(cleanTask({ ...TASK, points: [[-19.9, -43.9]] }), null); // leads precisa da pagina
  assert.equal(cleanTask({ ...TASK, points: [[-19.9, -43.9, 30]] }), null);
  const { mode, ...rk } = TASK;
  assert.equal(cleanTask({ ...rk, points: [[-19.9, -43.9, 0]] }), null); // ranking: so [lat, lng]
  assert.equal(cleanTask({ ...rk, points: [[-19.9, -43.9]] }).mode, undefined);
  assert.equal(appPrefix(TASK), "/leads");
  assert.equal(appPrefix(rk), "/ranking");
});

function fakeApp(responses) {
  const calls = [];
  const fn = async (url, options) => {
    calls.push({ url, body: options.body ? JSON.parse(options.body) : null, options });
    const r = responses.shift();
    return { status: r.status, json: async () => r.body };
  };
  fn.calls = calls;
  return fn;
}
const PING_OK = { status: 204, body: null };
const APP_PAGE = { url: "http://127.0.0.1:8000/leads/busca?id=3", tab: { id: 40 } };
const SEARCH = { id: "ext", url: "https://www.google.com/maps/search/dentista/@-19,-43,13z", tab: { id: 7 } };

function router(fetchFn, rankings, events = [], tabs = []) {
  return createRouter({ extensionId: "ext", optionsUrl: "chrome-extension://ext/options.html", arming: {},
    getSecret: async () => "s".repeat(40), fetchFn, createTab: async (url) => { tabs.push(url); return { id: 99 }; },
    mapsUrl: () => null, urls: {}, runner: { role: () => null, opening: () => false }, rankings, ranking,
    closeTab: async (id) => events.push(["close", id]), focusTab: async (id) => events.push(["focus", id]) });
}

test("clique na tela: o app manda a tarefa; a aba da busca coleta, pula paginas e volta para o app", async () => {
  const fetchFn = fakeApp([PING_OK, { status: 200, body: { ok: true, task: TASK } },
                           { status: 200, body: { ok: true, received: 2, total: 3, skip: 1 } },
                           { status: 200, body: { ok: true, status: "pronta" } }]);
  const rankings = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} });
  const opened = [];
  const r = await leadsRun({ msg: { type: "seals:leads-run", id: 3 }, sender: APP_PAGE, rankings, ranking,
    getSecret: async () => "s".repeat(40), fetchFn, openTab: async (url) => { opened.push(url); return { id: 7 }; } });
  assert.deepEqual(r, { ok: true });
  assert.deepEqual(opened, [TASK.searchUrl]);
  assert.deepEqual(fetchFn.calls[1].body, { id: 3 });
  assert.equal(fetchFn.calls[1].url, "http://127.0.0.1:8000/leads/tarefa");
  const events = [], tabs = [];
  const route = router(fetchFn, rankings, events, tabs);
  const role = (await route({ type: "seals:role?" }, SEARCH)).role;
  assert.equal(role.kind, "ranking");
  assert.equal(role.mode, "leads");
  const point = await route({ type: "seals:ranking-point", i: 0, text: "x" }, SEARCH);
  assert.deepEqual(point, { ok: true, received: 2, total: 3, skip: 1 });
  assert.equal(fetchFn.calls[2].url, "http://127.0.0.1:8000/leads/ponto");
  assert.equal((await route({ type: "seals:ranking-end", cancelled: false, error: null }, SEARCH)).ok, true);
  assert.equal(fetchFn.calls[3].url, "http://127.0.0.1:8000/leads/fim");
  assert.deepEqual(events, [["focus", 40], ["close", 7]]);
  assert.deepEqual(tabs, []);
  for (const c of fetchFn.calls.slice(1)) assert.equal(c.options.headers["X-Seals-Secret"], "s".repeat(40));
});

test("clique na tela: outra origem, tarefa de ranking, outro numero ou endereco estranho nao abrem nada", async () => {
  const rankings = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} });
  const base = { rankings, ranking, getSecret: async () => "s".repeat(40), openTab: async () => assert.fail("abriu aba") };
  for (const sender of [{ url: "https://evil.example/", tab: { id: 1 } }, { url: "http://127.0.0.1:8001/x", tab: { id: 1 } },
                        { url: "http://127.0.0.1:8000/x" }]) {
    assert.equal(await leadsRun({ ...base, msg: { id: 3 }, sender, fetchFn: fakeApp([]) }), null, sender.url);
  }
  assert.equal((await leadsRun({ ...base, msg: { id: "3" }, sender: APP_PAGE, fetchFn: fakeApp([]) })).ok, false);
  const { mode, ...rk } = TASK;
  for (const task of [{ ...rk, points: [[-19.9, -43.9]] }, { ...TASK, id: 4 }, { ...TASK, searchUrl: "https://evil.example/" }]) {
    const fetchFn = fakeApp([PING_OK, { status: 200, body: { ok: true, task } }]);
    assert.deepEqual(await leadsRun({ ...base, msg: { id: 3 }, sender: APP_PAGE, fetchFn }), { ok: false, error: "tarefa inesperada do app" });
  }
  const refused = fakeApp([PING_OK, { status: 409, body: { ok: false, error: "esta busca não está mais esperando." } }]);
  assert.deepEqual(await leadsRun({ ...base, msg: { id: 3 }, sender: APP_PAGE, fetchFn: refused }),
    { ok: false, error: "esta busca não está mais esperando." });
});

test("skip do app: so inteiro pequeno; aba parada avisa /leads/fim", async () => {
  const rankings = createRankingRegistry({ setTimer: () => 0, clearTimer: () => {} });
  rankings.register(7, TASK, 40);
  for (const [skip, want] of [[2, 2], [0, 0], [-1, 0], [99, 0], ["1", 0], [undefined, 0]]) {
    const fetchFn = fakeApp([{ status: 200, body: { ok: true, received: 1, total: 3, skip } }]);
    const r = await router(fetchFn, rankings)({ type: "seals:ranking-point", i: 0, text: "x" }, SEARCH);
    assert.equal(r.skip, want, String(skip));
  }
  const fetchFn = fakeApp([{ status: 200, body: { ok: true } }]);
  await rankingTimeout({ entry: rankings.entry(7), getSecret: async () => "s".repeat(40), fetchFn });
  assert.equal(fetchFn.calls[0].url, "http://127.0.0.1:8000/leads/fim");
});
