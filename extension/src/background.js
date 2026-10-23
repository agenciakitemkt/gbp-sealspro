// Service worker. Unico ponto que le o segredo (chrome.storage.local), fala com o app local (127.0.0.1) e abre abas.
importScripts("lib/cid.js", "lib/urls.js", "lib/ranking.js", "lib/run.js");

const { createArming, createRouter, createJobRunner, handleActionClick, rankingTimeout, rankingRun, leadsRun } = self.__sealsRun;
const arming = createArming(chrome.storage.session);
const getSecret = async () => (await chrome.storage.local.get("sealsSecret")).sealsSecret || "";

function badge(tabId, text, title) {
  chrome.action.setBadgeText({ tabId, text });
  chrome.action.setTitle({ tabId, title });
}

// Clique no icone da barra (alternativa ao botao dentro da pagina).
chrome.action.onClicked.addListener((tab) => {
  handleActionClick({ tab, arming, badge, sendToTab: (id, msg) => chrome.tabs.sendMessage(id, msg) });
});

// Coletas de ranking em andamento, por aba. Sem sinal por 90 s: o app marca a analise como erro.
const rankings = self.__sealsRanking.createRankingRegistry({
  onTimeout: (entry) => rankingTimeout({ entry, getSecret, fetchFn: (url, options) => fetch(url, options) }),
});

const route = createRouter({
  extensionId: chrome.runtime.id,
  optionsUrl: chrome.runtime.getURL("options.html"),
  arming,
  getSecret,
  fetchFn: (url, options) => fetch(url, options),
  createTab: (url) => chrome.tabs.create({ url }),
  mapsUrl: self.__sealsCid.mapsUrl,
  urls: self.__sealsUrls,
  rankings,
  ranking: self.__sealsRanking,
  closeTab: (id) => chrome.tabs.remove(id),
  focusTab: (id) => chrome.tabs.update(id, { active: true }),
  runner: createJobRunner({
    createTab: (url) => chrome.tabs.create({ url, active: true }),
    removeTab: (id) => chrome.tabs.remove(id),
    focusTab: (id) => chrome.tabs.update(id, { active: true }),
  }),
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const answer = route(msg, sender);
  if (!answer) return false;
  answer.then(sendResponse, () => sendResponse({ ok: false }));
  return true;
});

// Clique em "Analisar" (Analise de Ranking) ou "Buscar" (Busca de Leads) na tela do app. O Chrome so entrega
// mensagens de paginas listadas em externally_connectable (so http://127.0.0.1:8000/*); rankingRun e leadsRun conferem
// de novo a origem e so recebem o numero da analise ou da busca: o que buscar vem do app, com o segredo.
chrome.runtime.onMessageExternal.addListener((msg, sender, sendResponse) => {
  if (!msg || (msg.type !== "seals:ranking-run" && msg.type !== "seals:leads-run")) return false;
  const run = msg.type === "seals:leads-run" ? leadsRun : rankingRun;
  const answer = run({ msg, sender, rankings, ranking: self.__sealsRanking, getSecret,
    fetchFn: (url, options) => fetch(url, options), openTab: (url) => chrome.tabs.create({ url, active: true }) });
  if (!answer) return false;
  answer.then(sendResponse, () => sendResponse({ ok: false, error: "erro na extensão" }));
  return true;
});
