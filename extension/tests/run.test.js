const test = require("node:test");
const assert = require("node:assert/strict");
const { createArming, sanitizeCapture, buildRequest, submitCapture, ping, ARM_TTL_MS } = require("../src/lib/run.js");

function memoryStore() {
  const data = {};
  return {
    async get(key) { return key in data ? { [key]: data[key] } : {}; },
    async set(obj) { Object.assign(data, obj); },
    async remove(key) { delete data[key]; },
  };
}

function fakeFetch(status = 200, body = { id: 7, url: "/pre?id=7" }) {
  const calls = [];
  const fn = async (url, options) => { calls.push({ url, options }); return { ok: status < 400, status, json: async () => body }; };
  fn.calls = calls;
  return fn;
}

const CAPTURE = { capturedAt: "2026-10-09T12:00:00Z", place: ")]}'\n[]", reviews: ["p1"], photosOwner: null,
                  photosVideos: [], search: null, extensionErrors: [] };

test("sem clique para a aba, nada e enviado", async () => {
  const arming = createArming(memoryStore());
  const fetchFn = fakeFetch();
  await assert.rejects(submitCapture({ capture: CAPTURE, tabId: 3, arming, getSecret: async () => "s".repeat(43), fetchFn }), /sem clique/);
  await arming.arm(4); // clique em OUTRA aba
  await assert.rejects(submitCapture({ capture: CAPTURE, tabId: 3, arming, getSecret: async () => "s".repeat(43), fetchFn }), /sem clique/);
  assert.equal(fetchFn.calls.length, 0);
});

test("o clique vale uma vez e expira", async () => {
  let clock = 0;
  const arming = createArming(memoryStore(), () => clock);
  const fetchFn = fakeFetch();
  const args = { capture: CAPTURE, tabId: 3, arming, getSecret: async () => "s".repeat(43), fetchFn };
  await arming.arm(3);
  const r = await submitCapture(args);
  assert.deepEqual(r, { id: 7, url: "http://127.0.0.1:8000/pre?id=7" });
  await assert.rejects(submitCapture(args), /sem clique/); // nao reenvia
  await arming.arm(3);
  clock = ARM_TTL_MS + 1;
  await assert.rejects(submitCapture(args), /sem clique/);
  assert.equal(fetchFn.calls.length, 1);
});

test("pedido vai so para 127.0.0.1, com o segredo no cabecalho e sem cookies", async () => {
  const arming = createArming(memoryStore());
  const fetchFn = fakeFetch();
  await arming.arm(3);
  await submitCapture({ capture: CAPTURE, tabId: 3, arming, getSecret: async () => "segredo-".repeat(5), fetchFn });
  const { url, options } = fetchFn.calls[0];
  assert.equal(url, "http://127.0.0.1:8000/pre/captura");
  assert.equal(options.headers["X-Seals-Secret"], "segredo-".repeat(5));
  assert.equal(options.headers["Content-Type"], "application/json");
  assert.equal(options.credentials, "omit");
  assert.equal(options.redirect, "error");
  assert.deepEqual(Object.keys(JSON.parse(options.body)).sort(), [...Object.keys(CAPTURE), "diagnostics", "profileFtid", "socialLinks", "photos360", "reviewsLowest", "reviewsSearch"].sort());
});

test("sem segredo configurado nao envia", async () => {
  const arming = createArming(memoryStore());
  const fetchFn = fakeFetch();
  await arming.arm(3);
  await assert.rejects(submitCapture({ capture: CAPTURE, tabId: 3, arming, getSecret: async () => "", fetchFn }), /segredo/);
  assert.equal(fetchFn.calls.length, 0);
});

test("captura: so as chaves esperadas e so texto", () => {
  const clean = sanitizeCapture({ ...CAPTURE, cookies: "x", extra: [1] });
  assert.ok(!("cookies" in clean) && !("extra" in clean));
  assert.throws(() => sanitizeCapture({ ...CAPTURE, reviews: [{ x: 1 }] }), /reviews/);
  assert.throws(() => sanitizeCapture({ ...CAPTURE, place: ["x"] }), /place/);
  assert.throws(() => sanitizeCapture([]), /invalida/);
  assert.throws(() => sanitizeCapture({ ...CAPTURE, profileFtid: "<script>" }), /profileFtid/);
  assert.equal(sanitizeCapture({ ...CAPTURE, profileFtid: "0x1a:0x2b" }).profileFtid, "0x1a:0x2b");
});

test("resposta inesperada do app e erro, e o id vem so como numero", async () => {
  for (const body of [{ id: "1;javascript:alert(1)" }, {}, { id: -1 }]) {
    const arming = createArming(memoryStore());
    await arming.arm(3);
    await assert.rejects(submitCapture({ capture: CAPTURE, tabId: 3, arming, getSecret: async () => "s".repeat(43), fetchFn: fakeFetch(200, body) }), /inesperada/);
  }
  const arming = createArming(memoryStore());
  await arming.arm(3);
  await assert.rejects(submitCapture({ capture: CAPTURE, tabId: 3, arming, getSecret: async () => "s".repeat(43), fetchFn: fakeFetch(403) }), /403/);
});

test("ping testa a configuracao sem enviar dados", async () => {
  const fetchFn = fakeFetch(204);
  assert.deepEqual(await ping({ getSecret: async () => "s".repeat(43), fetchFn }), { ok: true, status: 204 });
  assert.equal(fetchFn.calls[0].url, "http://127.0.0.1:8000/pre/ping");
  assert.equal(fetchFn.calls[0].options.body, "{}");
  assert.deepEqual(await ping({ getSecret: async () => "", fetchFn }), { ok: false, status: 0 });
});

test("buildRequest nunca aponta para outro endereco", () => {
  assert.match(buildRequest({}, "x").url, /^http:\/\/127\.0\.0\.1:8000\//);
});

// ---------- clique no icone e mensagens ----------
const { handleActionClick, createRouter, isMaps, isSearch } = require("../src/lib/run.js");
const { mapsUrl } = require("../src/lib/cid.js");

function badges() {
  const list = [];
  const fn = (tabId, text, title) => list.push({ tabId, text, title });
  fn.list = list;
  return fn;
}

test("icone: com tab.url vazio (sem a permissao tabs) manda a mensagem e nao avisa se o content script responde", async () => {
  const arming = createArming(memoryStore());
  const sent = [];
  const badge = badges();
  const out = await handleActionClick({ tab: { id: 5, url: "" }, arming, badge,
    sendToTab: async (id, msg) => { sent.push({ id, msg }); return { ok: true }; } });
  assert.equal(out, "iniciada");
  assert.deepEqual(sent, [{ id: 5, msg: { type: "seals:start" } }]);
  assert.ok(badge.list.every((b) => b.text !== "!"));
  assert.equal(await arming.isArmed(5), true);
  const undef = await handleActionClick({ tab: { id: 6 }, arming, badge, sendToTab: async () => ({ ok: true }) });
  assert.equal(undef, "iniciada"); // sem tab.url nenhum
});

test("icone: so avisa quando ninguem responde, e desarma", async () => {
  const arming = createArming(memoryStore());
  const badge = badges();
  const out = await handleActionClick({ tab: { id: 5, url: "" }, arming, badge,
    sendToTab: async () => { throw new Error("Could not establish connection. Receiving end does not exist."); } });
  assert.equal(out, "sem-resposta");
  assert.equal(badge.list.at(-1).text, "!");
  assert.match(badge.list.at(-1).title, /Recarregue a página/);
  assert.equal(await arming.isArmed(5), false);
});

test("icone: captura ja em andamento", async () => {
  const arming = createArming(memoryStore());
  const out = await handleActionClick({ tab: { id: 5 }, arming, badge: badges(), sendToTab: async () => ({ ok: false, reason: "busy" }) });
  assert.equal(out, "ocupada");
});

const EXT = "abcdefghijklmnopabcdefghijklmnop";
function router(overrides = {}) {
  const tabs = [];
  const arming = createArming(memoryStore());
  const route = createRouter({
    extensionId: EXT, optionsUrl: `chrome-extension://${EXT}/options.html`, arming,
    getSecret: async () => "s".repeat(43), fetchFn: fakeFetch(), mapsUrl,
    createTab: async (url) => { tabs.push(url); return { id: 100 + tabs.length }; },
    ...overrides,
  });
  return { route, tabs, arming };
}
const fromSearch = { id: EXT, url: "https://www.google.com.br/search?q=oftalmologista", tab: { id: 1 } };
const fromMaps = (id) => ({ id: EXT, url: "https://www.google.com/maps/place/x", tab: { id } });

test("botao da busca: o service worker abre o Maps numa aba nova, que comeca a captura uma vez", async () => {
  const { route, tabs, arming } = router();
  assert.deepEqual(await route({ type: "seals:open-maps", cid: "1311862289879068560" }, fromSearch), { ok: true });
  assert.deepEqual(tabs, ["https://www.google.com/maps?cid=1311862289879068560&hl=pt-BR"]);
  assert.deepEqual(await route({ type: "seals:pending?" }, fromMaps(101)), { autostart: true });
  assert.deepEqual(await route({ type: "seals:pending?" }, fromMaps(101)), { autostart: false }); // so uma vez
  assert.deepEqual(await route({ type: "seals:pending?" }, fromMaps(7)), { autostart: false });   // outra aba
  assert.equal(await arming.isArmed(101), true);
});

test("botao da busca: CID invalido nao abre nada; so a pagina de busca pode pedir", async () => {
  const { route, tabs } = router();
  assert.deepEqual(await route({ type: "seals:open-maps", cid: "1&q=x" }, fromSearch), { ok: false, error: "cid invalido" });
  assert.equal(route({ type: "seals:open-maps", cid: "1311862289879068560" }, fromMaps(1)), null);
  assert.equal(route({ type: "seals:open-maps", cid: "1311862289879068560" }, { ...fromSearch, id: "outra" }), null);
  assert.equal(route({ type: "seals:open-maps", cid: "1311862289879068560" },
    { ...fromSearch, url: "https://www.google.com.evil.example/search?q=x" }), null);
  assert.equal(tabs.length, 0);
});

test("botao no Maps: libera a aba e a captura pode ser enviada uma vez", async () => {
  const { route, tabs } = router();
  assert.deepEqual(await route({ type: "seals:begin" }, fromMaps(9)), { ok: true });
  const capture = { capturedAt: "2026-10-09T12:00:00Z", place: "x" };
  assert.deepEqual(await route({ type: "seals:submit", capture }, fromMaps(9)), { ok: true, id: 7 });
  assert.deepEqual(tabs, ["http://127.0.0.1:8000/pre?id=7"]);
  assert.equal((await route({ type: "seals:submit", capture }, fromMaps(9))).ok, false); // sem novo clique
  assert.equal(route({ type: "seals:begin" }, fromSearch), null);
});

test("enderecos aceitos", () => {
  assert.ok(isMaps("https://www.google.com/maps/place/x") && isMaps("https://www.google.com/maps?cid=1"));
  assert.ok(!isMaps("https://www.google.com/mapsx") && !isMaps("https://www.google.com.br/maps/place/x"));
  assert.ok(isSearch("https://www.google.com/search?q=x") && isSearch("https://www.google.com.br/search?q=x"));
  assert.ok(!isSearch("https://www.google.com/searchx?q=1") && !isSearch("https://google.com/search?q=x"));
});

test("checagem antes de capturar: segredo, app fora do ar, recusa e ok", async () => {
  const { readiness } = require("../src/lib/run.js");
  const secret = async () => "s".repeat(43);
  assert.match((await readiness({ getSecret: async () => "", fetchFn: fakeFetch(204) })).message, /segredo não configurado/);
  const down = async () => { throw new TypeError("Failed to fetch"); };
  assert.match((await readiness({ getSecret: secret, fetchFn: down })).message, /não respondeu/);
  assert.match((await readiness({ getSecret: secret, fetchFn: fakeFetch(403) })).message, /recusou/);
  assert.deepEqual(await readiness({ getSecret: secret, fetchFn: fakeFetch(204) }), { ok: true });
});

test("checagem: so a aba do Maps pergunta, e nenhum dado do perfil e enviado", async () => {
  const fetchFn = fakeFetch(204);
  const { route } = router({ fetchFn });
  assert.deepEqual(await route({ type: "seals:ready?" }, fromMaps(3)), { ok: true });
  assert.equal(fetchFn.calls[0].url, "http://127.0.0.1:8000/pre/ping");
  assert.equal(fetchFn.calls[0].options.body, "{}");
  assert.equal(route({ type: "seals:ready?" }, fromSearch), null);
});

// ---------- abas controladas ----------
const { createJobRunner, buildJobs, OWNER_CODE, VIDEO_CODE } = require("../src/lib/run.js");
const urls = require("../src/lib/urls.js");

function fakeTabs() {
  const log = [];
  let next = 200;
  return {
    log,
    createTab: async (url) => { const id = next++; log.push(["create", id, url]); return { id }; },
    removeTab: async (id) => { log.push(["remove", id]); },
    focusTab: async (id) => { log.push(["focus", id]); },
  };
}

const PLACE_URL = "https://www.google.com/maps/place/X/@-19.94,-43.96,16z/data=!4m6!3m5!1s0x1a:0x2b!8m2!3d-19.9012345!4d-43.9012345!16s%2Fg%2Fx?hl=pt-BR";
const INFO = { category: "Agência de marketing digital", lat: -19.9012345, lng: -43.9012345, codes: ["CgIgAQ==", OWNER_CODE, VIDEO_CODE] };

test("tarefas: galeria so das categorias que existem na fonte A, e a busca", () => {
  const jobs = buildJobs({ placeUrl: PLACE_URL, info: INFO }, urls);
  assert.deepEqual(jobs.map((j) => j.key), ["photosOwner", "photosVideos", "search"]);
  assert.ok(jobs[0].url.includes("!1BCgIgARICEAE!") && jobs[1].url.includes("!1BCgIgARICCAQ!"));
  assert.match(jobs[2].url, /^https:\/\/www\.google\.com\/maps\/search\/Ag%C3%AAncia\+de\+marketing\+digital\/@-19\.9012345,-43\.9012345,13z\?hl=pt-BR$/);
  assert.deepEqual(buildJobs({ placeUrl: PLACE_URL, info: { ...INFO, codes: [] } }, urls).map((j) => j.key), ["search"]);
  assert.deepEqual(buildJobs({ placeUrl: "https://evil.example/x", info: { codes: [OWNER_CODE] } }, urls), []);
});

test("abas controladas: uma de cada vez, fecha e volta para a aba do perfil", async () => {
  const tabs = fakeTabs();
  const runner = createJobRunner({ ...tabs, timeoutMs: 1000 });
  const jobs = buildJobs({ placeUrl: PLACE_URL, info: INFO }, urls);
  const pending = runner.run(9, jobs);
  for (const id of [200, 201, 202]) {
    await new Promise((r) => setTimeout(r, 5));
    const role = runner.role(id);
    assert.ok(role, `aba ${id} sem tarefa`);
    assert.equal(runner.role(id + 1), null); // so uma aba aberta por vez
    runner.part(id, role.kind === "search" ? ["busca"] : ["galeria"]);
  }
  const out = await pending;
  assert.deepEqual(out.results, { photosOwner: ["galeria"], photosVideos: ["galeria"], search: ["busca"] });
  assert.deepEqual(tabs.log.filter((l) => l[0] !== "create"), [["remove", 200], ["focus", 9], ["remove", 201], ["focus", 9], ["remove", 202], ["focus", 9]]);
});

test("aba controlada que nao responde desiste; sinal de vida adia; lixo e recusado", async () => {
  const tabs = fakeTabs();
  const runner = createJobRunner({ ...tabs, timeoutMs: 40 });
  const pending = runner.run(9, [{ key: "search", kind: "search", url: "https://www.google.com/maps/search/x/@1,2,13z", maxPages: 3, label: "x" },
                                 { key: "photosOwner", kind: "photos", url: "https://www.google.com/maps/place/x", maxPages: 3, label: "y" }]);
  await new Promise((r) => setTimeout(r, 25));
  assert.equal(runner.alive(200), true);
  await new Promise((r) => setTimeout(r, 25));
  assert.ok(runner.role(200), "sinal de vida manteve a aba");
  runner.part(200, [{ nao: "texto" }]);
  const out = await pending; // a segunda nunca responde
  assert.deepEqual(out.results, { search: null, photosOwner: null });
  assert.equal(out.errors.length, 2);
  assert.match(out.errors[1].message, /não respondeu/);
});

test("mensagens das abas controladas so valem para quem tem tarefa e durante captura liberada", async () => {
  const tabs = fakeTabs();
  const runner = createJobRunner({ ...tabs, timeoutMs: 1000 });
  const { route, arming } = router({ runner, urls });
  assert.deepEqual(await route({ type: "seals:extra", placeUrl: PLACE_URL, info: INFO }, fromMaps(9)),
    { ok: false, error: "sem clique no botao para esta aba" });
  assert.deepEqual(await route({ type: "seals:role?" }, fromMaps(55)), { role: null, pending: false });
  assert.deepEqual(await route({ type: "seals:part", pages: ["x"] }, fromMaps(55)), { ok: false });
  await arming.arm(9);
  const pending = route({ type: "seals:extra", placeUrl: PLACE_URL, info: { ...INFO, codes: [] } }, fromMaps(9));
  await new Promise((r) => setTimeout(r, 5));
  assert.equal((await route({ type: "seals:role?" }, fromMaps(200))).role.key, "search");
  await route({ type: "seals:part", pages: ["p1"] }, fromMaps(200));
  const out = await pending;
  assert.deepEqual(out.planned, ["search"]);
  assert.deepEqual(out.results, { search: ["p1"] });
});

// ---------- redes sociais (bloco "Perfis" do painel da busca) ----------
const { cleanSocialLinks } = require("../src/lib/run.js");

test("redes sociais: so http(s), sem repetir, no maximo 10; nao lista = null", () => {
  assert.deepEqual(cleanSocialLinks(["https://www.instagram.com/x/", "javascript:alert(1)", "https://www.instagram.com/x/",
    7, "http://www.linkedin.com/in/x", "https://a b", "https://" + "a".repeat(300)]),
  ["https://www.instagram.com/x/", "http://www.linkedin.com/in/x"]);
  assert.equal(cleanSocialLinks(Array.from({ length: 15 }, (_, i) => `https://x.com/${i}`)).length, 10);
  assert.deepEqual(cleanSocialLinks([]), []);
  assert.equal(cleanSocialLinks(undefined), null);
  assert.equal(cleanSocialLinks("https://x.com/a"), null);
});

test("redes sociais: lidas na busca vao junto da captura, preenchidas so pelo service worker", async () => {
  const fetchFn = fakeFetch();
  const { route } = router({ fetchFn });
  await route({ type: "seals:open-maps", cid: "1311862289879068560",
                socialLinks: ["https://www.instagram.com/x/", "javascript:alert(1)"] }, fromSearch);
  await route({ type: "seals:pending?" }, fromMaps(101));
  const capture = { capturedAt: "2026-10-09T12:00:00Z", place: "x", socialLinks: ["https://falso.example/"] };
  assert.deepEqual(await route({ type: "seals:submit", capture }, fromMaps(101)), { ok: true, id: 7 });
  assert.deepEqual(JSON.parse(fetchFn.calls[0].options.body).socialLinks, ["https://www.instagram.com/x/"]);
});

test("redes sociais: captura que comeca no Maps leva null (nao avaliado), mesmo se a aba mandar links", async () => {
  const fetchFn = fakeFetch();
  const { route } = router({ fetchFn });
  await route({ type: "seals:begin" }, fromMaps(9));
  const capture = { capturedAt: "2026-10-09T12:00:00Z", place: "x", socialLinks: ["https://www.instagram.com/x/"] };
  await route({ type: "seals:submit", capture }, fromMaps(9));
  assert.equal(JSON.parse(fetchFn.calls[0].options.body).socialLinks, null);
});

// ---------- fotos 360 (categoria "Street View e 360°") ----------
test("tarefas: categoria 360 entra quando existe na fonte A, com o codigo sem o = final", () => {
  const { PANO_CODE } = require("../src/lib/run.js");
  const jobs = buildJobs({ placeUrl: PLACE_URL, info: { ...INFO, codes: [...INFO.codes, PANO_CODE] } }, urls);
  assert.deepEqual(jobs.map((j) => j.key), ["photosOwner", "photosVideos", "photos360", "search"]);
  const pano = jobs.find((j) => j.key === "photos360");
  assert.ok(pano.url.includes("!1BCgIgARICCAI!"));
  assert.equal(pano.kind, "photos");
});

test("captura: photos360 so como lista de textos", () => {
  assert.deepEqual(sanitizeCapture({ ...CAPTURE, photos360: ["p"] }).photos360, ["p"]);
  assert.throws(() => sanitizeCapture({ ...CAPTURE, photos360: [1] }), /photos360/);
});

test("aba controlada em criacao: avisa que ha tarefa a caminho ate ela ser registrada", async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  const runner = createJobRunner({ createTab: async () => { await gate; return { id: 300 }; }, removeTab: async () => {}, focusTab: async () => {}, timeoutMs: 1000 });
  assert.equal(runner.opening(), false);
  const pending = runner.run(9, [{ key: "photosOwner", kind: "photos", url: "https://www.google.com/maps/x", maxPages: 1 }]);
  await new Promise((r) => setTimeout(r, 5));
  assert.equal(runner.opening(), true);   // a aba ja pode existir e perguntar: ainda sem tarefa registrada
  release();
  await new Promise((r) => setTimeout(r, 5));
  assert.equal(runner.opening(), false);
  assert.equal(runner.role(300).key, "photosOwner");
  runner.part(300, ["p"]);
  await pending;
});

// ---------- amostra de avaliacoes lida na busca ----------
const { cleanReviewsSearch } = require("../src/lib/run.js");

test("amostra da busca: so texto no formato esperado, ate 5 paginas por lista", () => {
  const pg = ")]}'\n[]";
  assert.deepEqual(cleanReviewsSearch({ lowest: [pg], newest: [] }), { lowest: [pg], newest: [] });
  assert.equal(cleanReviewsSearch({ lowest: [], newest: [] }), null);
  assert.equal(cleanReviewsSearch({ lowest: ["<html>"], newest: [] }), null);
  assert.equal(cleanReviewsSearch({ lowest: Array(14).fill(pg), newest: [] }), null);
  assert.equal(cleanReviewsSearch([pg]), null);
  assert.equal(cleanReviewsSearch(null), null);
});

test("amostra da busca vai junto da captura, preenchida so pelo service worker", async () => {
  const fetchFn = fakeFetch();
  const { route } = router({ fetchFn });
  const pg = ")]}'\n[]";
  await route({ type: "seals:open-maps", cid: "1311862289879068560", reviewsSearch: { lowest: [pg], newest: [pg] } }, fromSearch);
  await route({ type: "seals:pending?" }, fromMaps(101));
  await route({ type: "seals:submit", capture: { capturedAt: "2026-10-10T12:00:00Z", place: "x", reviewsSearch: "falso" } }, fromMaps(101));
  assert.deepEqual(JSON.parse(fetchFn.calls[0].options.body).reviewsSearch, { lowest: [pg], newest: [pg] });
});
