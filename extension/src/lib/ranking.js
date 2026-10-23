// Analise de Ranking (CLAUDE.md, secao 16) e Busca de Leads (secao 18). Puro e testado; usado pelo content script do
// Maps e pelo service worker.
// - A tarefa (pontos da grade) vem do app pelo service worker e e validada aqui antes de qualquer pedido.
// - Cada ponto e a mesma busca que o Maps fez ao abrir a pagina (o <link> de preload tbm=map), trocando so a
//   distancia de visao e as coordenadas do parametro pb (!1d<metros>!2d<lng>!3d<lat>) e, na busca de leads, a pagina
//   (!8i<inicio>, logo depois de !7i20). Nada alem disso muda.
(function (root) {
  "use strict";
  const TEMPLATE_PREFIX = "https://www.google.com/search?tbm=map&";
  const SEARCH_PREFIX = "https://www.google.com/maps/search/";
  const VIEW = /%211d[0-9.]+%212d-?[0-9.]+%213d-?[0-9.]+/;
  const MAX_POINTS = 225; // 15x15
  const MAX_KEYWORD = 80;
  const MODES = ["ranking", "leads"]; // ranking: pontos [lat, lng]; leads: [lat, lng, inicio da pagina]
  const MAX_OFFSET = 100;
  const ROLE_TIMEOUT_MS = 90 * 1000; // sem nenhum ponto nesse tempo: a coleta e dada como parada

  const finite = (v) => typeof v === "number" && Number.isFinite(v);
  const validCoords = (lat, lng) => finite(lat) && finite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;

  /** O modelo do pedido: endereco da busca do proprio Google, com o trecho do ponto de vista que sera trocado. */
  function isPointTemplate(href) {
    return typeof href === "string" && href.length <= 6000 && href.startsWith(TEMPLATE_PREFIX) && VIEW.test(href);
  }

  /** Endereco da busca num ponto (e, com offset, a pagina que comeca nesse resultado). Null se o modelo ou os numeros
   *  nao forem os esperados. */
  function pointUrl(template, lat, lng, view, offset = 0) {
    if (!isPointTemplate(template) || !validCoords(lat, lng) || !finite(view) || view < 100 || view > 20000) return null;
    if (!validOffset(offset)) return null;
    let url = template.replace(VIEW, `%211d${Math.round(view)}%212d${lng.toFixed(7)}%213d${lat.toFixed(7)}`);
    if (offset > 0) {
      if (!url.includes("%217i20") || /%218i\d/.test(url)) return null; // pagina de 20 e sem pagina marcada
      url = url.replace("%217i20", `%217i20%218i${offset}`);
    }
    return url;
  }

  function validOffset(v) { return Number.isInteger(v) && v >= 0 && v <= MAX_OFFSET && v % 20 === 0; }

  /** Tarefa que vem do app: {id, keyword, view, points: [[lat, lng], ...], searchUrl} e, na busca de leads,
   *  mode "leads" com points [[lat, lng, inicio], ...]. Null se algo nao bater. */
  function cleanTask(t) {
    if (!t || typeof t !== "object" || Array.isArray(t)) return null;
    const mode = t.mode === undefined ? "ranking" : t.mode;
    if (!MODES.includes(mode)) return null;
    const width = mode === "leads" ? 3 : 2;
    const id = t.id;
    if (!Number.isInteger(id) || id <= 0) return null;
    if (typeof t.keyword !== "string" || !t.keyword.trim() || t.keyword.length > MAX_KEYWORD) return null;
    if (!finite(t.view) || t.view < 100 || t.view > 20000) return null;
    if (!Array.isArray(t.points) || !t.points.length || t.points.length > MAX_POINTS) return null;
    const points = [];
    for (const p of t.points) {
      if (!Array.isArray(p) || p.length !== width || !validCoords(p[0], p[1])) return null;
      if (width === 3 && !validOffset(p[2])) return null;
      points.push(p.slice());
    }
    if (typeof t.searchUrl !== "string" || !t.searchUrl.startsWith(SEARCH_PREFIX) || t.searchUrl.length > 400) return null;
    const out = { id, keyword: t.keyword, view: t.view, points, searchUrl: t.searchUrl };
    if (mode === "leads") out.mode = "leads";
    return out;
  }

  /** Rota do app para os pedidos da coleta: /ranking/... ou /leads/... */
  const appPrefix = (task) => (task && task.mode === "leads" ? "/leads" : "/ranking");

  /** Abas em coleta de ranking ou de leads (no service worker). Cada uma tem a analise (id), a etapa e, quando a coleta comecou
   *  pelo clique no app, a aba do app (para voltar a ela no fim):
   *  - "center": aba aberta pela extensao no perfil do cliente; le os dados do perfil e pede a tarefa ao app;
   *  - "points": aba da busca, com a tarefa (pontos) validada. */
  function createRankingRegistry({ setTimer = setTimeout, clearTimer = clearTimeout, timeoutMs = ROLE_TIMEOUT_MS,
                                   onTimeout = () => {} } = {}) {
    const tabs = new Map(); // tabId -> { id, stage, task, appTabId, timer }
    function touch(tabId) {
      const e = tabs.get(tabId);
      if (!e) return false;
      clearTimer(e.timer);
      e.timer = setTimer(() => { tabs.delete(tabId); onTimeout(e); }, timeoutMs);
      return true;
    }
    function set(tabId, entry) {
      const old = tabs.get(tabId);
      if (old) clearTimer(old.timer);
      tabs.set(tabId, { ...entry, timer: null });
      touch(tabId);
    }
    return {
      /** Aba aberta pela extensao (clique no app): ainda sem a tarefa, so o numero da analise. */
      opened(tabId, id, appTabId) { set(tabId, { id, stage: "center", task: null, appTabId }); },
      /** Tarefa validada: a aba passa a coletar os pontos (mantem a aba do app, se houver; numa sequencia de
       *  palavras-chave, a aba do app vem da palavra anterior). */
      register(tabId, task, appTabId) {
        const old = tabs.get(tabId);
        set(tabId, { id: task.id, stage: "points", task,
                     appTabId: appTabId !== undefined ? appTabId : old ? old.appTabId : null });
      },
      entry(tabId) { return tabs.get(tabId) || null; },
      task(tabId) { const e = tabs.get(tabId); return e && e.stage === "points" ? e.task : null; },
      role(tabId) {
        const e = tabs.get(tabId);
        if (!e) return null;
        return e.stage === "center" ? { kind: "ranking-center", id: e.id } : { kind: "ranking", ...e.task };
      },
      touch,
      remove(tabId) { const e = tabs.get(tabId); if (e) { clearTimer(e.timer); tabs.delete(tabId); } return e || null; },
    };
  }

  /** Endereco do perfil que o app manda abrir: so https://www.google.com/maps?cid=<numero>&hl=pt-BR. */
  function isProfileUrl(url) {
    return typeof url === "string" && /^https:\/\/www\.google\.com\/maps\?cid=\d{1,25}&hl=pt-BR$/.test(url);
  }

  const api = { isPointTemplate, pointUrl, cleanTask, createRankingRegistry, isProfileUrl, appPrefix, TEMPLATE_PREFIX,
                SEARCH_PREFIX, MAX_POINTS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsRanking = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
