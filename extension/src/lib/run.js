// Service worker: e o UNICO lugar que fala com o app local e o unico que le o segredo.
// O pedido sai daqui com a origem chrome-extension://<id>; do content script ele levaria a origem do Google e o
// Chrome bloquearia o acesso de pagina publica a rede local.
(function (root) {
  "use strict";
  const APP = "http://127.0.0.1:8000";
  const ARM_TTL_MS = 15 * 60 * 1000; // o clique vale por 15 minutos para aquela aba
  const MAX_BODY = 20 * 1024 * 1024;
  const CAPTURE_KEYS = ["capturedAt", "place", "reviews", "reviewsLowest", "photosOwner", "photosVideos", "photos360", "search", "extensionErrors",
                        "diagnostics", "profileFtid"];

  /** Guarda "esta aba recebeu o clique" (storage.session: so contextos confiaveis da extensao). Uma aba por vez.
   *  autostart: a aba do Maps foi aberta pelo botao da busca e deve comecar a captura sozinha, uma vez.
   *  socialLinks: links do bloco "Perfis" do painel da busca, lidos no clique (null = a captura nao comecou pela busca). */
  function createArming(store, now = () => Date.now()) {
    const read = async () => (await store.get("sealsArmed")).sealsArmed;
    const valid = (a, tabId) => !!a && a.tabId === tabId && now() - a.at <= ARM_TTL_MS;
    return {
      async arm(tabId, { autostart = false, socialLinks = null, reviewsSearch = null } = {}) {
        await store.set({ sealsArmed: { tabId, at: now(), autostart, socialLinks, reviewsSearch } });
      },
      async disarm() { await store.remove("sealsArmed"); },
      async isArmed(tabId) { return valid(await read(), tabId); },
      async socialLinks(tabId) { const a = await read(); return valid(a, tabId) ? a.socialLinks ?? null : null; },
      async reviewsSearch(tabId) { const a = await read(); return valid(a, tabId) ? a.reviewsSearch ?? null : null; },
      async takeAutostart(tabId) {
        const a = await read();
        if (!valid(a, tabId) || !a.autostart) return false;
        await store.set({ sealsArmed: { ...a, autostart: false } });
        return true;
      },
    };
  }

  const isMaps = (url) => typeof url === "string" && /^https:\/\/www\.google\.com\/maps(\/|\?|$)/.test(url);
  const isSearch = (url) => typeof url === "string" && /^https:\/\/www\.google\.com(\.br)?\/search(\?|$)/.test(url);

  const OWNER_CODE = "CgIgARICEAE=";  // "Do proprietario" na fonte A (igual nos 9 perfis mapeados)
  const VIDEO_CODE = "CgIgARICCAQ=";  // "Videos"
  const PANO_CODE = "CgIgARICCAI=";   // "Street View e 360°"
  const JOB_TIMEOUT_MS = 90 * 1000;   // sem resposta da aba controlada (nem sinal de vida) nesse tempo: desiste
  const MAX_JOB_BYTES = 12 * 1024 * 1024;

  const MAX_SOCIAL = 10;

  /** Links do bloco "Perfis" vindos da busca: so http(s), sem repetir, no maximo 10. Nao e lista: null. */
  function cleanSocialLinks(list) {
    if (!Array.isArray(list)) return null;
    const out = [];
    for (const href of list) {
      if (typeof href !== "string" || href.length > 300 || !/^https?:\/\/[^\s]+$/i.test(href) || out.includes(href)) continue;
      out.push(href);
      if (out.length === MAX_SOCIAL) break;
    }
    return out;
  }

  /** Amostra de avaliacoes lida na busca: {lowest, newest}, ate 5 paginas de texto cada, no formato ")]}'". */
  function cleanReviewsSearch(v) {
    if (!v || typeof v !== "object" || Array.isArray(v)) return null;
    const ok = (l) => Array.isArray(l) && l.length <= 13 &&
      l.every((t) => typeof t === "string" && t.length <= 400000 && t.startsWith(")]}'"));
    if (!ok(v.lowest) || !ok(v.newest) || !(v.lowest.length || v.newest.length)) return null;
    return { lowest: v.lowest.slice(), newest: v.newest.slice() };
  }

  const cleanPages = (pages) => (Array.isArray(pages) && pages.every((t) => typeof t === "string")
    && pages.reduce((n, t) => n + t.length, 0) <= MAX_JOB_BYTES ? pages : null);

  /** Diagnostico de uma aba controlada: so textos curtos (caminhos de pedidos, rotulos de botoes, tamanhos). */
  function cleanDiagnostics(d) {
    if (!d || typeof d !== "object") return null;
    const str = (v, n) => (typeof v === "string" ? v.slice(0, n) : null);
    const list = (v, n, m) => (Array.isArray(v) ? v.filter((x) => typeof x === "string").slice(0, n).map((x) => x.slice(0, m)) : []);
    return { key: str(d.key, 20), url: str(d.url, 120), container: str(d.container, 30), pages: Number(d.pages) || 0,
             requests: list(d.requests, 60, 140), labels: list(d.labels, 40, 40) };
  }

  /** Abas controladas (galeria por categoria e busca dos concorrentes), uma de cada vez: abre a aba ativa (a lista so
   *  carrega rolando numa aba visivel), espera a captura dela, fecha e volta para a aba do perfil. */
  function createJobRunner({ createTab, removeTab, focusTab, setTimer = setTimeout, clearTimer = clearTimeout,
                             timeoutMs = JOB_TIMEOUT_MS }) {
    const jobs = new Map(); // tabId -> { job, finish, timer }

    function arm(entry) {
      clearTimer(entry.timer);
      entry.timer = setTimer(() => entry.finish({ pages: null, reason: "a aba controlada não respondeu a tempo" }), timeoutMs);
    }

    let opening = 0; // abas controladas sendo criadas: a aba nova pode perguntar a tarefa antes de ela ser registrada

    async function runOne(mainTabId, job) {
      let tab;
      opening++;
      try {
        tab = await createTab(job.url);
      } catch (e) {
        opening--;
        return { pages: null, reason: "não foi possível abrir a aba" };
      }
      const result = await new Promise((resolve) => {
        const entry = { job, finish: null, timer: null };
        entry.finish = (r) => { clearTimer(entry.timer); jobs.delete(tab.id); resolve(r); };
        jobs.set(tab.id, entry);
        opening--; // so depois de registrar: a aba nova nao fica sem tarefa nem sem o aviso de "em criacao"
        arm(entry);
      });
      try { await removeTab(tab.id); } catch (e) { /* ja fechada */ }
      try { await focusTab(mainTabId); } catch (e) { /* aba do perfil fechada */ }
      return result;
    }

    return {
      async run(mainTabId, list) {
        const results = {};
        const errors = [];
        const diagnostics = [];
        for (const job of list) {
          const r = await runOne(mainTabId, job);
          results[job.key] = cleanPages(r.pages);
          if (!results[job.key]) errors.push({ key: job.key, message: r.reason || "sem dados" });
          if (r.diagnostics) diagnostics.push(r.diagnostics);
        }
        return { results, errors, diagnostics };
      },
      opening() { return opening > 0; },
      role(tabId) {
        const e = jobs.get(tabId);
        return e ? { key: e.job.key, kind: e.job.kind, maxPages: e.job.maxPages, label: e.job.label, code: e.job.code || null } : null;
      },
      alive(tabId) { const e = jobs.get(tabId); if (e) arm(e); return !!e; },
      part(tabId, pages, reason, diagnostics) {
        const e = jobs.get(tabId);
        if (!e) return false;
        e.finish({ pages, reason: typeof reason === "string" ? reason.slice(0, 200) : undefined,
                   diagnostics: cleanDiagnostics(diagnostics) });
        return true;
      },
    };
  }

  /** Monta as tarefas das abas controladas a partir da leitura minima da fonte A. Tudo validado aqui. */
  function buildJobs({ placeUrl, info }, { galleryUrl, searchUrl }) {
    const list = [];
    const codes = Array.isArray(info && info.codes) ? info.codes : [];
    for (const [key, code, label, maxPages] of [["photosOwner", OWNER_CODE, "fotos do proprietário", 30],
                                                 ["photosVideos", VIDEO_CODE, "vídeos", 8],
                                                 ["photos360", PANO_CODE, "fotos 360°", 3]]) {
      if (!codes.includes(code)) continue; // categoria nao existe no perfil: o app decide pela fonte A
      const url = galleryUrl(placeUrl, code);
      if (url && isMaps(url)) list.push({ key, kind: "photos", url, label, maxPages, code: code.replace(/=+$/, "") });
    }
    const url = info && searchUrl(info.category, info.lat, info.lng, info.city, info.uf);
    // Ate 6 paginas (cerca de 120 resultados), como o GBP Check
    if (url && isMaps(url)) list.push({ key: "search", kind: "search", url, label: "concorrentes", maxPages: 6 });
    return list;
  }

  /** Checagem antes de capturar: segredo salvo e app aceitando ID e segredo. Nao envia dados do perfil. */
  async function readiness({ getSecret, fetchFn }) {
    if (!(await getSecret())) {
      return { ok: false, message: "segredo não configurado. Abra as opções da extensão, cole o segredo e salve." };
    }
    let r;
    try {
      r = await ping({ getSecret, fetchFn });
    } catch (e) {
      return { ok: false, message: "o app local não respondeu. Ele está rodando (./.venv/bin/python serve.py)?" };
    }
    if (r.ok) return { ok: true };
    if (r.status === 403) {
      return { ok: false, message: "o app recusou a extensão. Confira o ID (coletar.py id-extensao) e o segredo nas opções." };
    }
    return { ok: false, message: `o app respondeu de forma inesperada (${r.status}).` };
  }

  /** Clique no icone da barra: nao depende de tab.url (vem vazio sem a permissao "tabs"). Manda a mensagem ao
   *  content script da aba e so avisa se ninguem responder. */
  async function handleActionClick({ tab, arming, sendToTab, badge }) {
    if (!tab || tab.id === undefined) return "sem-aba";
    await arming.arm(tab.id);
    let answer;
    try {
      answer = await sendToTab(tab.id, { type: "seals:start" });
    } catch (e) {
      answer = undefined;
    }
    if (answer && answer.ok) { badge(tab.id, "", "SealsPro: capturar a pré análise deste perfil"); return "iniciada"; }
    if (answer) { badge(tab.id, "…", "SealsPro: já há uma captura em andamento nesta aba"); return "ocupada"; }
    await arming.disarm();
    badge(tab.id, "!", "SealsPro: a extensão não está ativa nesta aba. Recarregue a página do Google Maps " +
      "(www.google.com/maps) ou use o botão Pré Análise SealsPro na página, e tente de novo.");
    return "sem-resposta";
  }

  /** Mensagens dos content scripts e da pagina de opcoes. Devolve uma Promise com a resposta, ou null se a
   *  mensagem nao e para o service worker (ou nao veio de um lugar permitido). */
  function createRouter({ extensionId, optionsUrl, arming, getSecret, fetchFn, createTab, mapsUrl, runner, urls,
                          rankings = null, ranking = null, closeTab = async () => {}, focusTab = async () => {} }) {
    return function route(msg, sender) {
      if (!msg || !sender || sender.id !== extensionId || typeof sender.url !== "string") return null;
      const tabId = sender.tab && sender.tab.id;
      switch (msg.type) {
        case "seals:open-maps": { // botao da busca: abre o perfil no Maps numa aba nova e a captura comeca la
          if (tabId === undefined || !isSearch(sender.url)) return null;
          const url = mapsUrl(msg.cid);
          if (!url) return Promise.resolve({ ok: false, error: "cid invalido" });
          const socialLinks = cleanSocialLinks(msg.socialLinks);
          const reviewsSearch = cleanReviewsSearch(msg.reviewsSearch);
          return createTab(url).then(async (tab) => {
            await arming.arm(tab.id, { autostart: true, socialLinks, reviewsSearch });
            return { ok: true };
          });
        }
        case "seals:extra": { // da aba do perfil, durante uma captura liberada: galeria por categoria e concorrentes
          if (tabId === undefined || !isMaps(sender.url) || !runner) return null;
          return arming.isArmed(tabId).then((armed) => {
            if (!armed) return { ok: false, error: "sem clique no botao para esta aba" };
            const list = buildJobs({ placeUrl: msg.placeUrl, info: msg.info }, urls);
            return runner.run(tabId, list).then((r) => ({ ok: true, planned: list.map((j) => j.key), ...r }));
          });
        }
        case "seals:role?": // aba controlada perguntando o que fazer
          if (tabId === undefined || !isMaps(sender.url) || !runner) return null;
          if (rankings && rankings.role(tabId)) return Promise.resolve({ role: rankings.role(tabId), pending: false });
          return Promise.resolve({ role: runner.role(tabId), pending: runner.opening() });
        case "seals:ranking-begin": // botao "Ranking SealsPro" no perfil (clique de verdade): o app devolve a tarefa
          if (tabId === undefined || !isMaps(sender.url) || !rankings || !ranking) return null;
          return rankingBegin({ place: msg.place, tabId, rankings, ranking, getSecret, fetchFn, closeTab });
        case "seals:ranking-point": // um ponto da grade, da aba em coleta
          if (tabId === undefined || !isMaps(sender.url) || !rankings) return null;
          return rankingPoint({ msg, tabId, rankings, getSecret, fetchFn });
        case "seals:ranking-end":
          if (tabId === undefined || !isMaps(sender.url) || !rankings) return null;
          return rankingEnd({ msg, tabId, rankings, ranking, getSecret, fetchFn, createTab, closeTab, focusTab });
        case "seals:alive":
          if (tabId === undefined || !runner) return null;
          return Promise.resolve({ ok: runner.alive(tabId) });
        case "seals:part":
          if (tabId === undefined || !isMaps(sender.url) || !runner) return null;
          return Promise.resolve({ ok: runner.part(tabId, msg.pages, msg.reason, msg.diagnostics) });
        case "seals:ready?": // antes de qualquer passo: da para enviar?
          if (tabId === undefined || !isMaps(sender.url)) return null;
          return readiness({ getSecret, fetchFn });
        case "seals:begin": // botao dentro do Maps (clique de verdade): libera esta aba
          if (tabId === undefined || !isMaps(sender.url)) return null;
          return arming.arm(tabId).then(() => ({ ok: true }));
        case "seals:pending?": // aba aberta pelo botao da busca: comecar sozinha (uma vez)
          if (tabId === undefined || !isMaps(sender.url)) return null;
          return arming.takeAutostart(tabId).then((autostart) => ({ autostart }));
        case "seals:submit":
          if (tabId === undefined || !isMaps(sender.url)) return null;
          return submitCapture({ capture: msg.capture, tabId, arming, getSecret, fetchFn })
            .then((r) => createTab(r.url).then(() => ({ ok: true, id: r.id })))
            .catch((e) => ({ ok: false, error: e.message }));
        case "seals:ping":
          if (!sender.url.startsWith(optionsUrl)) return null;
          return ping({ getSecret, fetchFn }).catch(() => ({ ok: false, status: 0 }));
        default:
          return null;
      }
    };
  }

  /** So as chaves esperadas; textos e listas de textos. Devolve a captura limpa ou lanca erro. */
  function sanitizeCapture(capture) {
    if (!capture || typeof capture !== "object" || Array.isArray(capture)) throw new Error("captura invalida");
    const out = {};
    for (const key of CAPTURE_KEYS) {
      const v = capture[key];
      if (v === undefined || v === null) { out[key] = null; continue; }
      if (key === "extensionErrors") { out[key] = Array.isArray(v) ? v.slice(0, 20) : []; continue; }
      if (key === "diagnostics") { out[key] = Array.isArray(v) ? v.slice(0, 5).map(cleanDiagnostics).filter(Boolean) : []; continue; }
      if (key === "profileFtid") {
        if (typeof v !== "string" || !/^0x[0-9a-f]{1,16}:0x[0-9a-f]{1,16}$/.test(v)) throw new Error("campo profileFtid invalido");
        out[key] = v;
        continue;
      }
      if (key === "capturedAt" || key === "place") {
        if (typeof v !== "string") throw new Error(`campo ${key} invalido`);
        out[key] = v;
        continue;
      }
      if (!Array.isArray(v) || !v.every((t) => typeof t === "string")) throw new Error(`campo ${key} invalido`);
      out[key] = v;
    }
    return out;
  }

  function buildRequest(capture, secret, path = "/pre/captura") {
    return {
      url: APP + path,
      options: {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Seals-Secret": secret },
        body: JSON.stringify(capture),
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
      },
    };
  }

  /** Envia a captura do content script da aba `tabId`. Recusa sem clique valido ou sem segredo configurado. */
  async function submitCapture({ capture, tabId, arming, getSecret, fetchFn }) {
    if (!(await arming.isArmed(tabId))) throw new Error("sem clique no botao para esta aba");
    const socialLinks = await arming.socialLinks(tabId);
    const reviewsSearch = await arming.reviewsSearch(tabId);
    await arming.disarm();
    const secret = await getSecret();
    if (!secret) throw new Error("segredo nao configurado nas opcoes da extensao");
    const clean = sanitizeCapture(capture);
    clean.socialLinks = socialLinks; // so o service worker preenche (lido na busca, no clique); a aba do Maps nao
    clean.reviewsSearch = reviewsSearch; // idem: amostra de avaliacoes lida na busca
    const req = buildRequest(clean, secret);
    if (req.options.body.length > MAX_BODY) throw new Error("captura grande demais");
    const resp = await fetchFn(req.url, req.options);
    if (!resp.ok) throw new Error(`app recusou (${resp.status})`);
    const data = await resp.json();
    const id = Number(data && data.id);
    if (!Number.isInteger(id) || id <= 0) throw new Error("resposta inesperada do app");
    return { id, url: `${APP}/pre?id=${id}` };
  }

  async function ping({ getSecret, fetchFn }) {
    const secret = await getSecret();
    if (!secret) return { ok: false, status: 0 };
    const req = buildRequest({}, secret, "/pre/ping");
    const resp = await fetchFn(req.url, req.options);
    return { ok: resp.status === 204, status: resp.status };
  }

  // ---------- Analise de Ranking (secao 16) ----------
  const MAX_POINT_TEXT = 3 * 1024 * 1024;

  /** POST para o app com o segredo; devolve {status, data}. */
  async function postApp({ path, body, getSecret, fetchFn }) {
    const secret = await getSecret();
    if (!secret) throw new Error("segredo não configurado nas opções da extensão");
    const req = buildRequest(body, secret, path);
    if (req.options.body.length > MAX_BODY) throw new Error("pedido grande demais");
    const resp = await fetchFn(req.url, req.options);
    let data = null;
    try { data = await resp.json(); } catch (e) { data = null; }
    return { status: resp.status, data };
  }

  async function rankingBegin({ place, tabId, rankings, ranking, getSecret, fetchFn, closeTab = async () => {} }) {
    const opened = rankings && rankings.entry(tabId); // aba aberta pela extensao (clique no app): a analise e essa
    const fail = async (error) => {
      if (opened && opened.stage === "center") { // o app mostra o motivo na tela; a aba aberta pela extensao fecha
        rankings.remove(tabId);
        await postApp({ path: "/ranking/fim", body: { id: opened.id, cancelled: false, error }, getSecret, fetchFn }).catch(() => null);
      }
      return { ok: false, error };
    };
    if (typeof place !== "string" || !place || place.length > MAX_JOB_BYTES) {
      return fail("os dados do perfil ainda não chegaram. Espere a página carregar e clique de novo.");
    }
    let r;
    const body = opened && opened.stage === "center" ? { place, id: opened.id } : { place };
    try {
      r = await postApp({ path: "/ranking/inicio", body, getSecret, fetchFn });
    } catch (e) {
      return { ok: false, error: e.message === "segredo não configurado nas opções da extensão" ? e.message
        : "o app local não respondeu. Ele está rodando (./.venv/bin/python serve.py)?" };
    }
    if (r.status === 403) return { ok: false, error: "o app recusou a extensão. Confira o ID e o segredo nas opções." };
    if (!r.data || r.data.ok !== true) {
      return fail(r.data && typeof r.data.error === "string" ? r.data.error.slice(0, 300) : `o app respondeu ${r.status}`);
    }
    const task = ranking.cleanTask(r.data.task);
    if (!task) return fail("tarefa inesperada do app");
    rankings.register(tabId, task);
    return { ok: true, url: task.searchUrl, points: task.points.length };
  }

  /** Clique em "Analisar" na tela do app (mensagem externa, so de http://127.0.0.1:8000, conferido aqui e pelo Chrome
   *  em externally_connectable). A mensagem traz so o numero da analise: o app, com o segredo, diz qual perfil abrir.
   *  A extensao abre o perfil numa aba nova e o resto segue como no botao "Ranking SealsPro". */
  async function rankingRun({ msg, sender, rankings, ranking, getSecret, fetchFn, openTab }) {
    if (!sender || typeof sender.url !== "string" || !sender.url.startsWith(APP + "/") || !sender.tab) return null;
    const id = msg && msg.id;
    if (!Number.isInteger(id) || id <= 0) return { ok: false, error: "análise inválida" };
    const ready = await readiness({ getSecret, fetchFn });
    if (!ready.ok) return { ok: false, error: ready.message };
    let r;
    try {
      r = await postApp({ path: "/ranking/tarefa", body: { id }, getSecret, fetchFn });
    } catch (e) {
      return { ok: false, error: "o app local não respondeu" };
    }
    if (!r.data || r.data.ok !== true) return { ok: false, error: (r.data && r.data.error) || `o app respondeu ${r.status}` };
    if (r.data.id !== id || !ranking.isProfileUrl(r.data.mapsUrl)) return { ok: false, error: "resposta inesperada do app" };
    let tab;
    try {
      tab = await openTab(r.data.mapsUrl);
    } catch (e) {
      return { ok: false, error: "não foi possível abrir o Maps" };
    }
    rankings.opened(tab.id, id, sender.tab.id);
    return { ok: true };
  }

  /** Clique em "Buscar" na tela da Busca de Leads (mensagem externa, so de http://127.0.0.1:8000, como rankingRun).
   *  A mensagem traz so o numero da busca: o app, com o segredo, devolve a tarefa (pedidos), validada aqui. A extensao
   *  abre a busca da palavra no Maps numa aba nova, que ja nasce coletando. */
  async function leadsRun({ msg, sender, rankings, ranking, getSecret, fetchFn, openTab }) {
    if (!sender || typeof sender.url !== "string" || !sender.url.startsWith(APP + "/") || !sender.tab) return null;
    const id = msg && msg.id;
    if (!Number.isInteger(id) || id <= 0) return { ok: false, error: "busca inválida" };
    const ready = await readiness({ getSecret, fetchFn });
    if (!ready.ok) return { ok: false, error: ready.message };
    let r;
    try {
      r = await postApp({ path: "/leads/tarefa", body: { id }, getSecret, fetchFn });
    } catch (e) {
      return { ok: false, error: "o app local não respondeu" };
    }
    if (!r.data || r.data.ok !== true) return { ok: false, error: (r.data && r.data.error) || `o app respondeu ${r.status}` };
    const task = ranking.cleanTask(r.data.task);
    if (!task || task.mode !== "leads" || task.id !== id) return { ok: false, error: "tarefa inesperada do app" };
    let tab;
    try {
      tab = await openTab(task.searchUrl);
    } catch (e) {
      await postApp({ path: "/leads/fim", body: { id, cancelled: false, error: "não foi possível abrir o Maps" },
                      getSecret, fetchFn }).catch(() => null);
      return { ok: false, error: "não foi possível abrir o Maps" };
    }
    rankings.register(tab.id, task, sender.tab.id);
    return { ok: true };
  }

  async function rankingPoint({ msg, tabId, rankings, getSecret, fetchFn }) {
    const task = rankings.task(tabId);
    if (!task) return { ok: false, error: "sem coleta de ranking nesta aba" };
    const i = msg.i;
    if (!Number.isInteger(i) || i < 0 || i >= task.points.length || typeof msg.text !== "string"
        || msg.text.length > MAX_POINT_TEXT) return { ok: false, error: "ponto inválido" };
    rankings.touch(tabId);
    try {
      const path = (task.mode === "leads" ? "/leads" : "/ranking") + "/ponto";
      const r = await postApp({ path, body: { id: task.id, i, text: msg.text }, getSecret, fetchFn });
      if (!r.data || !r.data.ok) return { ok: false, error: (r.data && r.data.error) || `o app respondeu ${r.status}` };
      // Busca de leads: pagina incompleta, as seguintes do mesmo ponto nao sao pedidas (o app diz quantas pular)
      const skip = Number.isInteger(r.data.skip) && r.data.skip > 0 && r.data.skip <= 10 ? r.data.skip : 0;
      return { ok: true, received: r.data.received, total: r.data.total, skip };
    } catch (e) {
      return { ok: false, error: "o app local não respondeu" };
    }
  }

  async function rankingEnd({ msg, tabId, rankings, ranking = null, getSecret, fetchFn, createTab,
                              closeTab = async () => {}, focusTab = async () => {} }) {
    const entry = rankings.remove(tabId);
    if (!entry || !entry.task) return { ok: false, error: "sem coleta de ranking nesta aba" };
    const body = { id: entry.id, cancelled: msg.cancelled === true,
                   error: typeof msg.error === "string" ? msg.error.slice(0, 300) : null };
    const leads = entry.task.mode === "leads";
    try {
      const r = await postApp({ path: leads ? "/leads/fim" : "/ranking/fim", body, getSecret, fetchFn });
      const ok = !!(r.data && r.data.ok);
      // Varias palavras-chave: o app ja iniciou a proxima do lote e manda a tarefa; a mesma aba segue para ela.
      const next = ok && ranking && !leads && r.data.next ? ranking.cleanTask(r.data.next) : null;
      if (next) {
        rankings.register(tabId, next, entry.appTabId);
        return { ok: true, status: r.data.status, next: next.searchUrl, keyword: next.keyword, points: next.points.length };
      }
      if (ok && entry.appTabId != null) { // comecou pelo app: fecha a aba do Maps e volta para a tela, que se atualiza
        try { await focusTab(entry.appTabId); } catch (e) { /* aba do app fechada */ }
        try { await closeTab(tabId); } catch (e) { /* ja fechada */ }
      } else if (ok) {
        await createTab(leads ? `${APP}/leads/busca?id=${entry.id}` : `${APP}/ranking/analise?id=${entry.id}`);
      }
      return { ok, status: r.data && r.data.status };
    } catch (e) {
      return { ok: false, error: "o app local não respondeu" };
    }
  }

  /** Coleta parada sem aviso (aba fechada ou travada): o app marca a analise como erro. */
  function rankingTimeout({ entry, getSecret, fetchFn }) {
    const leads = !!(entry.task && entry.task.mode === "leads");
    return postApp({ path: leads ? "/leads/fim" : "/ranking/fim", body: { id: entry.id, cancelled: false,
                                                    error: "A aba do Maps parou de responder durante a coleta." },
                     getSecret, fetchFn }).catch(() => null);
  }

  const api = { rankingBegin, rankingRun, leadsRun, rankingPoint, rankingEnd, rankingTimeout, postApp, cleanReviewsSearch, cleanSocialLinks, createJobRunner, buildJobs, OWNER_CODE, VIDEO_CODE, PANO_CODE, createArming, sanitizeCapture, buildRequest, submitCapture, ping, readiness, handleActionClick, createRouter,
                isMaps, isSearch, APP, ARM_TTL_MS, CAPTURE_KEYS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsRun = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
