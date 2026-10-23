// Content script (mundo ISOLATED) em https://www.google.com/maps/*.
// - Guarda as copias do hook so na memoria da pagina (buffer.js), descartadas ao sair dela.
// - So age depois do clique no botao da extensao: o service worker manda "seals:start" para esta aba.
// - Entrega a captura ao service worker (chrome.runtime.sendMessage). Nunca fala com 127.0.0.1 nem le o segredo.
// - Os seletores da interface do Maps sao heuristicos (rotulos em pt-BR): passo que nao achar o que precisa devolve
//   null e a fonte fica "nao avaliado" no app. Conferir a mao (CLAUDE.md, 13.10).
(function () {
  "use strict";
  const { classify } = globalThis.__sealsMatch;
  const { CaptureBuffer, attachLifecycle } = globalThis.__sealsBuffer;
  const { runSteps } = globalThis.__sealsSteps;
  const { createSession } = globalThis.__sealsSession;
  const { createSealsProButton, HOST_ID, RANKING } = globalThis.__sealsButton;
  const { isPointTemplate, pointUrl } = globalThis.__sealsRanking;
  const { placeInfo, placeForProfile, ftidFromUrl, galleryCategory, galleryEnd } = globalThis.__sealsUrls;
  /** Dados do perfil ABERTO: a ultima preview/place cujo identificador bate com o da URL. A mais recente de todas
   *  podia ser de outro local do mapa (aconteceu: um clube de futebol no lugar de uma imobiliaria). */
  const profilePlace = () => placeForProfile(buffer.since(0, "place"), location.href);

  const buffer = new CaptureBuffer();
  attachLifecycle(window, buffer);
  // Rastro dos pedidos da pagina ao Google (caminho e rpcids, sem conteudo), so na memoria, para diagnosticar as
  // abas controladas. Limitado e descartado ao sair da pagina, como o buffer.
  const trace = [];
  window.addEventListener("message", (e) => {
    if (e.source === window && e.data && e.data.__seals === 1 && typeof e.data.trace === "string" && trace.length < 120
        && !/\/(log204|gen_204|vt)\b|\/maps\/preview\/(pegman|lp|passiveassist)/.test(e.data.trace)) {
      trace.push(e.data.trace.slice(0, 140)); // sem o ruido de telemetria e de mapa
    }
  });
  window.addEventListener("pagehide", () => { trace.length = 0; });

  const WAIT_RESPONSE_MS = 9000;
  const MAX_PAGES = { reviews: 10, owner: 15, videos: 8, pano: 3 };
  let cancelled = false;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  /** sendMessage que nunca lanca (nem quando a extensao foi recarregada e esta aba ficou com o script antigo). */
  async function send(msg) {
    try {
      return await chrome.runtime.sendMessage(msg);
    } catch (e) {
      return null;
    }
  }
  const shortPause = () => sleep(1200 + Math.floor(Math.random() * 1300));

  // ---------- ajudas de DOM (so leitura de rotulos e cliques; nenhum innerHTML) ----------
  function textOf(el) {
    return ((el.getAttribute && el.getAttribute("aria-label")) || el.textContent || "").trim();
  }
  function findClickable(pattern, root = document) {
    const els = root.querySelectorAll('button, [role="button"], [role="tab"], [role="menuitemradio"], [role="menuitem"], a[role="button"]');
    for (const el of els) if (pattern.test(textOf(el)) && el.offsetParent !== null) return el;
    return null;
  }
  function scrollableAncestor(el) {
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (/(auto|scroll)/.test(s.overflowY) && n.scrollHeight > n.clientHeight + 10) return n;
    }
    return null;
  }
  async function waitFor(kind, afterSeq, count, timeout = WAIT_RESPONSE_MS) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      if (cancelled) throw new Error("cancelado");
      if (buffer.since(afterSeq, kind).length >= count) return true;
      await sleep(300);
    }
    return false;
  }
  const END_OF_LIST = /(chegou ao final da lista|reached the end of the list)/i;

  /** Rola em passos (com evento de roda, como uma pessoa) ate o fim do que esta carregado e espera a proxima pagina.
   *  Rolar de uma vez ate o fim nao fazia o Maps pedir mais resultados. Para no aviso de fim da lista. */
  /** Galeria (aba controlada): vai direto ao fundo da grade e espera a proxima pagina, ate a pagina marcar o fim, nada
   *  novo chegar em 5 tentativas ou o limite de paginas. Rolar em passos levava mais de 5 minutos em "Do proprietario"
   *  com 340 fotos (perfil de teste, 2026-10-10) e a aba era dada como sem resposta; indo ao fundo, 441 fotos em 29 s. A foto mais
   *  recente do dono estava na posicao 305: a ordem da categoria nao e por data, entao ler ate o fim importa. */
  async function scrollGallery(job, initial, from, isDone) {
    let current = initial;
    const live = () => {
      if (!current || !current.isConnected || current.clientHeight === 0) current = listContainer("photos") || current;
      return current;
    };
    let stuck = 0;
    while (!isDone() && stuck < 5 && jobPages(job, from).length < job.maxPages) {
      const have = jobPages(job, from).length;
      const box = live();
      box.scrollTop = box.scrollHeight;
      box.dispatchEvent(new WheelEvent("wheel", { deltaY: 300, bubbles: true, cancelable: true }));
      await sleep(1200 + Math.floor(Math.random() * 800));
      stuck = jobPages(job, from).length > have ? 0 : stuck + 1;
    }
  }

  async function scrollCollect(kind, initial, maxPages, isDone = () => false) {
    const start = buffer.seq;
    // O Maps pode redesenhar a lista depois que ela foi achada (o elemento sai da pagina e fica 0/0): busca de novo.
    let current = initial;
    const live = () => {
      if (kind !== "reviews" && (!current || !current.isConnected || current.clientHeight === 0)) current = listContainer(kind) || current;
      return current;
    };
    for (let page = 1; page < maxPages; page++) {
      if (isDone()) break; // a ultima pagina ja marcou o fim: nao fica rolando a toa
      if (buffer.since(start, kind).length >= maxPages - 1) break; // o limite vale em paginas recebidas, nao em voltas
      const have = buffer.since(start, kind).length;
      // Ate o fim de verdade (com limite): 12 passos nao bastavam numa lista de 11638 px e o Maps nunca pedia mais.
      for (let i = 0; i < 40 && live().scrollTop + live().clientHeight < live().scrollHeight - 4; i++) {
        const dy = Math.round(live().clientHeight * 0.8);
        live().dispatchEvent(new WheelEvent("wheel", { deltaY: dy, bubbles: true, cancelable: true }));
        live().scrollBy(0, dy);
        await sleep(350 + Math.floor(Math.random() * 300));
      }
      if (END_OF_LIST.test(live().textContent || "")) break;
      // No fundo: leva o ultimo item para a tela e faz pequenas subidas e descidas, como quem continua rolando,
      // ate o Maps pedir a proxima pagina (ou 12 s). So encostar no fundo uma vez nao disparava o carregamento.
      let arrived = false;
      for (let t = 0; t < 8 && !arrived; t++) {
        const last = live().querySelector('[role="feed"] > div:last-child, [role="article"]:last-of-type') || live().lastElementChild;
        if (last && last.scrollIntoView) last.scrollIntoView({ block: "end" });
        live().scrollTop = live().scrollHeight;
        live().dispatchEvent(new WheelEvent("wheel", { deltaY: 240, bubbles: true, cancelable: true }));
        arrived = await waitFor(kind, start, have + 1, 900);
        if (!arrived) {
          live().scrollBy(0, -260);
          await sleep(350);
          arrived = await waitFor(kind, start, have + 1, 300);
        }
        if (END_OF_LIST.test(live().textContent || "")) break;
      }
      if (!arrived && !(await waitFor(kind, start, have + 1, 3000))) break; // nada novo: fim da lista
      await shortPause();
    }
    return buffer.since(start, kind);
  }

  // ---------- passos ----------
  // Rotulos em portugues e ingles (o Maps do usuario pode estar em ingles): reserva quando a galeria pela URL falha.
  const GALLERY_LABELS = {
    photosOwner: /^(Do proprietário|From the owner|By owner)\b/i,
    photosVideos: /^(Vídeos|Videos)\b/i,
    photos360: /^Street View (e|&|and) 360/i,
  };

  let lastExtra = () => [];
  function buildSteps() {
    let extra = null; // resposta das abas controladas (galeria por categoria e concorrentes)
    const fromExtra = (key) => {
      const pages = extra && extra.results && extra.results[key];
      return Array.isArray(pages) && pages.length ? pages : null;
    };
    const extraReason = (key) => {
      const e = extra && (extra.errors || []).find((x) => x.key === key);
      return e ? e.message : (extra && extra.planned && !extra.planned.includes(key) ? null : "sem dados");
    };
    const planned = (key) => !!(extra && extra.planned && extra.planned.includes(key));
    lastExtra = () => (extra && extra.diagnostics) || [];
    const steps = [
      { key: "place", label: "Dados do perfil", run: async () => profilePlace() },
      { key: "reviews", label: "Avaliações (mais recentes)", run: stepReviews },
      { key: "reviewsLowest", label: "Avaliações (menor nota)", run: stepReviewsLowest },
      { key: "_extra", label: "Galeria e concorrentes (abas que fecham sozinhas)", run: async () => {
        extra = await send({ type: "seals:extra", placeUrl: location.href, info: placeInfo(profilePlace()) });
        if (!extra || !extra.ok) throw new Error((extra && extra.error) || "abas controladas indisponíveis");
        return null;
      } },
      { key: "photosOwner", label: "Fotos do proprietário", run: () => galleryStep("photosOwner", MAX_PAGES.owner) },
      { key: "photosVideos", label: "Vídeos", run: () => galleryStep("photosVideos", MAX_PAGES.videos) },
      { key: "photos360", label: "Fotos 360°", run: () => galleryStep("photos360", MAX_PAGES.pano) },
      { key: "search", label: "Concorrentes", run: async () => {
        const pages = fromExtra("search");
        if (!pages && planned("search")) throw new Error(`concorrentes: ${extraReason("search")}`);
        if (!pages) throw new Error("concorrentes: sem categoria ou coordenadas na fonte A");
        return pages;
      } },
    ];
    async function galleryStep(key, maxPages) {
      const pages = fromExtra(key);
      if (pages) return pages;
      if (!planned(key)) return null; // categoria nao existe no perfil (ou URL fora do formato): o app decide pela fonte A
      // A URL nao trouxe dados: reserva pelos botoes, nesta aba.
      const viaButtons = await stepGallery(GALLERY_LABELS[key], maxPages);
      if (viaButtons && viaButtons.length) return viaButtons;
      throw new Error(`${key}: pela URL (${extraReason(key)}) e pelos botões não vieram dados`);
    }
    const check = () => {
      if (!(document.documentElement.lang || "").toLowerCase().startsWith("pt")) {
        return "O Maps precisa estar em português (abra com ?hl=pt-BR) para a captura funcionar.";
      }
      if (!ftidFromUrl(location.href)) {
        return "Abra o perfil do negócio no Maps (o endereço precisa ser de um perfil, /maps/place/...) e tente de novo.";
      }
      if (!profilePlace()) {
        return "Os dados deste perfil não foram capturados. Recarregue a página do perfil (F5) e tente de novo.";
      }
      return null;
    };
    return { steps, check };
  }

  async function stepReviews() {
    const tab = findClickable(/^Avaliações/i);
    if (!tab) throw new Error("aba Avaliações não encontrada");
    tab.click();
    await shortPause();
    const sort = findClickable(/^(Classificar|Ordenar)/i);
    if (!sort) throw new Error("botão de ordenar não encontrado");
    sort.click();
    await shortPause();
    const newest = findClickable(/^Mais recentes$/i);
    if (!newest) throw new Error("opção Mais recentes não encontrada");
    const beforeSort = buffer.seq;
    newest.click();
    if (!(await waitFor("reviews", beforeSort, 1))) throw new Error("avaliações não chegaram");
    // Das mais recentes so a primeira pagina: ela da a data da ultima avaliacao. A amostra vem de "Menor
    // classificacao" (passo seguinte), como no GBP Check (comparacao ao vivo, 2026-10-10).
    return buffer.since(beforeSort, "reviews").slice(0, 1);
  }

  /** Amostra para sem resposta, com comentario e tendencia: ordenada por "Menor classificacao", ate 10 paginas. */
  async function stepReviewsLowest() {
    const sort = findClickable(/^(Classificar|Ordenar|Sort)/i);
    if (!sort) throw new Error("botão de ordenar não encontrado");
    sort.click();
    await shortPause();
    const lowest = findClickable(/^(Menor classificação|Lowest rating)$/i);
    if (!lowest) throw new Error("opção Menor classificação não encontrada");
    const beforeSort = buffer.seq;
    lowest.click();
    if (!(await waitFor("reviews", beforeSort, 1))) throw new Error("avaliações de menor nota não chegaram");
    const first = document.querySelector("[data-review-id]");
    const box = first && scrollableAncestor(first);
    if (box) await scrollCollect("reviews", box, MAX_PAGES.reviews);
    return buffer.since(beforeSort, "reviews").slice(0, MAX_PAGES.reviews);
  }

  async function openGallery() {
    if (findClickable(/^(Do proprietário|From the owner|Vídeos|Videos|Mais recentes|Latest)\b/i)) return true; // ja aberta
    const hero = document.querySelector('button[jsaction*="heroHeaderImage"], button[aria-label^="Foto"], button[aria-label^="Photo"]');
    if (!hero) return false;
    hero.click();
    await shortPause();
    return true;
  }

  async function stepGallery(categoryPattern, maxPages) {
    if (!(await openGallery())) throw new Error("galeria não encontrada");
    const category = findClickable(categoryPattern);
    if (!category) return null; // categoria nao existe no perfil: o app decide pela fonte A
    const start = buffer.seq;
    category.click();
    if (!(await waitFor("photos", start, 1))) throw new Error("fotos não chegaram");
    const item = document.querySelector("a[data-photo-index], [data-photo-index]");
    const box = item && scrollableAncestor(item);
    if (box) await scrollCollect("photos", box, maxPages);
    return buffer.since(start, "photos");
  }

  // ---------- faixa de progresso (textContent apenas) ----------
  let banner = null;
  function showBanner(text, done) {
    if (!banner) {
      banner = document.createElement("div");
      banner.style.cssText = "position:fixed;z-index:2147483647;top:12px;right:12px;max-width:340px;padding:10px 14px;" +
        "background:#0B0B0D;color:#F8FAFC;font:14px/1.4 system-ui,sans-serif;border:2px solid #14B8A6;border-radius:8px";
      const label = document.createElement("span");
      const button = document.createElement("button");
      button.textContent = "Cancelar";
      button.style.cssText = "margin-left:10px;background:#818CF8;border:0;border-radius:4px;padding:2px 8px;cursor:pointer";
      button.addEventListener("click", () => { cancelled = true; if (!session.isRunning()) hideBanner(); });
      banner.append(label, button);
      document.documentElement.appendChild(banner);
    }
    banner.firstChild.textContent = "SealsPro: " + text;
    banner.lastChild.textContent = done ? "Fechar" : "Cancelar";
  }
  function hideBanner() { if (banner) { banner.remove(); banner = null; } }

  // ---------- ligacoes ----------
  const session = createSession({
    buffer,
    classify,
    buildSteps,
    runSteps,
    getDiagnostics: () => lastExtra(),
    getExtras: () => ({ profileFtid: ftidFromUrl(location.href) }),
    submit: async (capture) => (await send({ type: "seals:submit", capture })) || { ok: false, error: "extensão indisponível: recarregue a página" },
  });

  window.addEventListener("message", (event) => {
    const accepted = session.onHookMessage(event, window);
    const d = event.data;
    if (!accepted && event.source === window && d && d.__seals === 1 && typeof d.kind === "string" && trace.length < 120) {
      trace.push(`recusado no buffer: ${d.kind} (${typeof d.text === "string" ? d.text.length : typeof d.text})` +
                 (buffer.overflow ? " [buffer cheio]" : ""));
    }
  });

  /** Aba aberta pelo botao da busca: os dados do perfil podem ainda nao ter chegado. Espera ate 15 s; se a pagina
   *  trouxe a preview/place como preload (hipotese a conferir), busca esse mesmo endereco do Google. */
  async function ensurePlace() {
    const end = Date.now() + 15000;
    while (Date.now() < end && !profilePlace()) await sleep(500);
    if (profilePlace()) return;
    const link = document.querySelector('link[href*="/maps/preview/place"]');
    const href = link && new URL(link.getAttribute("href"), location.href).href;
    if (href && classify(href) === "place") {
      try {
        const resp = await fetch(href, { credentials: "same-origin" });
        if (resp.ok) buffer.add("place", await resp.text());
      } catch (e) { /* sem os dados: a checagem avisa */ }
    }
  }

  async function startCapture() {
    if (session.isRunning()) return { ok: false, reason: "busy" };
    cancelled = false;
    showBanner("conferindo a conexão com o app…");
    const ready = await send({ type: "seals:ready?" });
    if (!ready || !ready.ok) {
      showBanner(`não foi possível: ${(ready && ready.message) || "extensão indisponível, recarregue a página."}`, true);
      return { ok: false, reason: "not-ready" };
    }
    showBanner("preparando…");
    await ensurePlace();
    const res = await session.start({
      sleep,
      isCancelled: () => cancelled,
      onProgress: (i, n, label) => showBanner(`passo ${i} de ${n}: ${label}…`),
    }).catch((e) => ({ ok: false, error: e.message }));
    if (res && res.ok) showBanner("pré análise enviada. O resultado abriu numa aba nova.", true);
    else showBanner(res && res.reason === "cancelled" ? "captura cancelada." : `não foi possível: ${(res && (res.reason || res.error)) || "erro"}`, true);
    return res;
  }

  // Clique no icone da barra: o service worker manda "seals:start" para esta aba.
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (sender.id !== chrome.runtime.id || !msg || msg.type !== "seals:start") return false;
    if (session.isRunning()) { sendResponse({ ok: false, reason: "busy" }); return false; }
    sendResponse({ ok: true }); // a captura segue sozinha; o resultado abre numa aba nova
    startCapture();
    return false;
  });

  // ---------- botao "Pre Analise SealsPro" no topo do painel do perfil ----------
  async function onButtonClick(button) {
    if (session.isRunning()) return;
    button.disabled = true;
    try {
      const answer = await send({ type: "seals:begin" });
      if (answer && answer.ok) await startCapture();
    } finally {
      button.disabled = false;
    }
  }

  function placeHeading() {
    // O Maps pode ter mais de um div[role=main] (paineis escondidos): vale o primeiro que tem um h1 visivel.
    for (const h1 of document.querySelectorAll('div[role="main"] h1')) if (h1.offsetParent !== null) return h1;
    return null;
  }

  function mountButton() {
    const h1 = placeHeading();
    const existing = document.getElementById(HOST_ID);
    const ranking = document.getElementById(RANKING.id);
    if (!h1) { if (existing) existing.remove(); if (ranking) ranking.remove(); return; }
    const anchor = h1.closest("div") || h1;
    if (existing && ranking && existing.nextElementSibling === ranking && ranking.nextElementSibling === anchor) return;
    if (existing) existing.remove();
    if (ranking) ranking.remove();
    anchor.parentElement.insertBefore(createSealsProButton(document, onButtonClick), anchor);
    anchor.parentElement.insertBefore(createSealsProButton(document, onRankingClick, RANKING), anchor);
  }

  // ---------- Analise de Ranking (secao 16): botao "Ranking SealsPro" no perfil e coleta na aba da busca ----------
  let rankingRunning = false;

  /** Clique de verdade no "Ranking SealsPro": manda os dados do perfil aberto ao app (pelo service worker), que confere se
   *  ha uma analise preparada para este cliente e devolve a tarefa. A aba segue para a busca da palavra. */
  async function onRankingClick(button) {
    if (session.isRunning() || rankingRunning) return;
    button.disabled = true;
    cancelled = false;
    try {
      showBanner("ranking: conferindo a conexão com o app…");
      const ready = await send({ type: "seals:ready?" });
      if (!ready || !ready.ok) {
        showBanner(`não foi possível: ${(ready && ready.message) || "extensão indisponível, recarregue a página."}`, true);
        return;
      }
      await ensurePlace();
      const answer = await send({ type: "seals:ranking-begin", place: profilePlace() || "" });
      if (!answer || !answer.ok || typeof answer.url !== "string" || !answer.url.startsWith("https://www.google.com/maps/search/")) {
        showBanner(`não foi possível: ${(answer && answer.error) || "extensão indisponível, recarregue a página."}`, true);
        return;
      }
      showBanner(`ranking: abrindo a busca (${answer.points} pontos)…`);
      location.assign(answer.url);
    } finally {
      button.disabled = false;
    }
  }

  /** Aba aberta pela extensao depois do clique em "Analisar" no app: espera o perfil carregar (o endereco
   *  /maps?cid= vira /maps/place/...), manda os dados dele e segue para a busca, como no botao "Ranking SealsPro". */
  async function runRankingCenter() {
    rankingRunning = true;
    cancelled = false;
    showBanner("ranking: abrindo o perfil do cliente…");
    const end = Date.now() + 20000;
    while (Date.now() < end && !location.pathname.startsWith("/maps/place/")) await sleep(500);
    await ensurePlace();
    const answer = await send({ type: "seals:ranking-begin", place: profilePlace() || "" });
    rankingRunning = false;
    if (!answer || !answer.ok || typeof answer.url !== "string" || !answer.url.startsWith("https://www.google.com/maps/search/")) {
      showBanner(`não foi possível: ${(answer && answer.error) || "extensão indisponível, recarregue a página."}`, true);
      return;
    }
    showBanner(`ranking: abrindo a busca (${answer.points} pontos)…`);
    location.assign(answer.url);
  }

  /** Busca do Maps num ponto: so o endereco montado a partir do modelo da propria pagina, sem cookies (sem a conta
   *  logada, para o resultado nao sair personalizado). */
  async function fetchPoint(url) {
    if (!isPointTemplate(url)) return "";
    const resp = await fetch(url, { credentials: "omit" });
    // Google pedindo verificacao (captcha): para a coleta em vez de seguir marcando pontos sem leitura
    if (resp.status === 429 || /\/sorry\//.test(resp.url || "")) throw new Error(BLOCKED);
    return resp.ok ? resp.text() : "";
  }
  const BLOCKED = "o Google pediu uma verificação (captcha) e a coleta parou. Espere algumas horas antes de rodar de novo.";

  async function pointTemplate() {
    const end = Date.now() + 15000;
    while (Date.now() < end) {
      const link = document.querySelector('link[href*="tbm=map"]');
      const href = link && new URL(link.getAttribute("href"), location.href).href;
      if (href && isPointTemplate(href)) return href;
      await sleep(500);
    }
    return null;
  }

  /** Aba da busca aberta pelo clique: um pedido por vez, com pausa de 1,2 a 2 s, cada um entregue ao service worker.
   *  Ranking: um pedido por ponto da grade. Busca de leads: ponto e pagina; o app diz quando pular as paginas que
   *  faltam de um ponto (a anterior veio incompleta). */
  async function runRanking(job) {
    if (!location.pathname.startsWith("/maps/search/")) return;
    rankingRunning = true;
    cancelled = false;
    let error = null;
    const n = job.points.length;
    const label = job.mode === "leads" ? "leads" : "ranking";
    showBanner(`${label} “${job.keyword}”: preparando…`);
    const template = await pointTemplate();
    if (!template) error = "a página da busca não trouxe o modelo do pedido (o formato do Maps pode ter mudado).";
    for (let i = 0; template && i < n && !cancelled; i++) {
      showBanner(job.mode === "leads" ? `leads “${job.keyword}”: pedido ${i + 1} de ${n}…`
        : `ranking “${job.keyword}”: ponto ${i + 1} de ${n}…`);
      const url = pointUrl(template, job.points[i][0], job.points[i][1], job.view, job.points[i][2] || 0);
      let text = "";
      for (let attempt = 0; attempt < 2 && !text && url; attempt++) {
        try { text = await fetchPoint(url); } catch (e) { if (e.message === BLOCKED) { error = BLOCKED; break; } text = ""; }
        if (!text) await sleep(3000);
      }
      if (error) break;
      const r = await send({ type: "seals:ranking-point", i, text });
      if (!r || !r.ok) { error = (r && r.error) || "o app não recebeu o ponto."; break; }
      if (Number.isInteger(r.skip) && r.skip > 0) i += r.skip;
      if (i < n - 1) await sleep(1200 + Math.floor(Math.random() * 800));
    }
    const end = await send({ type: "seals:ranking-end", cancelled, error });
    rankingRunning = false;
    if (end && end.ok && typeof end.next === "string" && end.next.startsWith("https://www.google.com/maps/search/")) {
      showBanner(`ranking: próxima palavra, “${String(end.keyword || "").slice(0, 80)}” (${end.points} pontos)…`);
      location.assign(end.next); // a aba recarrega na busca da proxima palavra e o service worker ja tem a tarefa
      return;
    }
    if (cancelled) showBanner(`${label} cancelado.`, true);
    else if (error) showBanner(`não foi possível: ${error}`, true);
    else showBanner(end && end.ok ? `${label} concluído. O resultado abriu no app.` : `${label} enviado, mas o app não confirmou.`, true);
  }

  let scheduled = false;
  function scheduleMount() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => { scheduled = false; mountButton(); }, 400);
  }

  // ---------- aba controlada (aberta pelo service worker durante uma captura) ----------
  const PRELOAD = { photos: 'link[href*="batchexecute"][href*="hspqX"]', search: 'link[href*="tbm=map"]' };

  function listContainer(kind) {
    // O elemento que rola e o painel em volta da lista (rolar o proprio [role=feed] nao carregava mais resultados).
    if (kind === "search") { const feed = document.querySelector('[role="feed"]'); return feed && (scrollableAncestor(feed) || feed); }
    // A grade de fotos ([data-photo-index]) primeiro: com uma lista de seletores, o querySelector devolve o primeiro
    // elemento do documento, que era uma imagem da faixa do visualizador, acima da grade (contêiner 0/0; teste de 2026-10-10).
    const item = document.querySelector("[data-photo-index]") ||
      document.querySelector('div[role="main"] img[src*="googleusercontent"], img[src*="googleusercontent"][src*="-k-no"]');
    return item && scrollableAncestor(item);
  }

  const JOB_LABELS = { photosOwner: GALLERY_LABELS.photosOwner, photosVideos: GALLERY_LABELS.photosVideos,
                       photos360: GALLERY_LABELS.photos360 };
  const OTHER_TILE = /^(Tudo|All|Mais recentes|Latest)\b/i;

  /** Galeria aberta pela URL sem a primeira pagina pela rede: clica em outro bloco de categoria e volta no desejado,
   *  para o Maps buscar as fotos pela rede. Devolve a posicao do buffer a partir da qual as paginas sao da categoria
   *  desejada (a pagina do outro bloco, que tambem chega pela rede, fica de fora), ou null se nada chegou. */
  async function clickTiles(job) {
    const target = JOB_LABELS[job.key];
    if (!target) return null;
    const other = findClickable(OTHER_TILE);
    if (other) { other.click(); await shortPause(); }
    const tile = findClickable(target);
    if (!tile) return null;
    const start = buffer.seq;
    tile.click();
    return (await waitForJob(job, start, 12000).catch(() => false)) ? start : null;
  }

  /** Paginas da tarefa depois de `from`. Na galeria, so as da categoria pedida ([13] da pagina; o codigo vem sem o
   *  "=" final, como na URL): ficam de fora a do bloco clicado na reserva e a do visualizador do Street View. */
  function jobPages(job, from) {
    const pages = buffer.since(from, job.kind);
    if (job.kind !== "photos" || !job.code) return pages;
    return pages.filter((t) => { const c = galleryCategory(t); return !!c && c.replace(/=+$/, "") === job.code; });
  }

  async function waitForJob(job, from, timeout) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      if (jobPages(job, from).length) return true;
      await sleep(300);
    }
    return false;
  }

  function diagnostics(job, box, from = 0) {
    const labels = [...document.querySelectorAll('button, [role="button"], [role="tab"]')]
      .filter((el) => el.offsetParent !== null).map(textOf).filter((t) => t && t.length <= 40).slice(0, 40);
    return { key: job.key, url: location.pathname.slice(0, 60) + (location.pathname.includes("!14m1!1B") ? " [com categoria]" : ""),
             requests: trace.slice(0, 60),
             container: box ? `${box.scrollHeight}/${box.clientHeight} rolado ate ${Math.round(box.scrollTop + box.clientHeight)}${END_OF_LIST.test(box.textContent || "") ? " [fim da lista]" : ""}` : "nenhum",
             labels, pages: jobPages(job, from).length };
  }

  async function runJob(job) {
    showBanner(`coletando ${job.label}… esta aba fecha sozinha.`);
    const heartbeat = setInterval(() => send({ type: "seals:alive" }), 8000);
    try {
      // A primeira pagina precisa chegar pela rede (sem rolar); se ela vier embutida no HTML, faltariam itens.
      let ok = await waitForJob(job, 0, 15000).catch(() => false);
      if (!ok) {
        const link = document.querySelector(PRELOAD[job.kind]);
        const href = link && new URL(link.getAttribute("href"), location.href).href;
        if (href && classify(href) === job.kind) {
          try {
            const resp = await fetch(href, { credentials: "same-origin" });
            if (resp.ok) buffer.add(job.kind, await resp.text());
          } catch (e) { /* segue sem */ }
        }
        ok = jobPages(job, 0).length > 0;
      }
      let from = 0; // so valem as paginas da categoria pedida
      if (!ok && job.kind === "photos") {
        const start = await clickTiles(job);
        if (start !== null) { from = start; ok = true; }
      }
      if (!ok) {
        await send({ type: "seals:part", pages: null, reason: "a primeira página não chegou pela rede",
                     diagnostics: diagnostics(job, listContainer(job.kind)) });
        return;
      }
      // A grade da galeria e desenhada depois que a primeira pagina chega: espera por ela (ate 6 s) para nao cair
      // na reserva, que acha uma imagem fora da grade (conteiner 0/0, sem rolar; teste de 2026-10-10).
      for (let i = 0; job.kind === "photos" && i < 20 && !document.querySelector("[data-photo-index]"); i++) await sleep(300);
      const box = listContainer(job.kind);
      const ended = () => { const pages = jobPages(job, from); return job.kind === "photos" && pages.length > 0 && galleryEnd(pages[pages.length - 1]); };
      if (box && !ended()) {
        if (job.kind === "photos") await scrollGallery(job, box, from, ended);
        else await scrollCollect(job.kind, box, job.maxPages, ended);
      }
      await send({ type: "seals:part", pages: jobPages(job, from).slice(0, job.maxPages + 2),
                   diagnostics: diagnostics(job, listContainer(job.kind) || box, from) });
    } finally {
      clearInterval(heartbeat);
    }
  }

  async function askRole() {
    // Corrida com a criacao da aba: o service worker so registra a tarefa depois que a aba existe. 4 s nao bastaram
    // numa captura logo apos recarregar a extensao (a aba ficou parada e a tarefa desistiu em 90 s): ate 15 s.
    for (let i = 0; i < 30; i++) {
      const answer = await send({ type: "seals:role?" });
      if (answer && answer.role) return answer.role;
      if (!answer || (!answer.pending && i >= 7)) return null; // aba comum: desiste em 4 s, como antes
      await sleep(500);
    }
    return null;
  }

  async function boot() {
    const job = await askRole();
    if (job) {
      if (job.kind === "ranking") runRanking(job);
      else if (job.kind === "ranking-center") runRankingCenter();
      else runJob(job);
      return;
    }
    new MutationObserver(scheduleMount).observe(document.body, { childList: true, subtree: true });
    scheduleMount();
    // Aberta pelo botao da busca? O service worker diz uma unica vez. So pergunta quando a pagina ja e o perfil
    // (/maps/place/...): /maps?cid=... ainda vai trocar de endereco, e perguntar ali gastaria o inicio automatico.
    // Tentativas por ate ~12 s (corrida com a criacao da aba e com a troca de endereco).
    (async () => {
      for (let i = 0; i < 15; i++) {
        if (location.pathname.startsWith("/maps/place/")) {
          const answer = await send({ type: "seals:pending?" });
          if (answer && answer.autostart) { startCapture(); return; }
        }
        await sleep(800);
      }
    })();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { boot(); }, { once: true });
  else boot();
})();
