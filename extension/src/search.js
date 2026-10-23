// Content script (ISOLATED) na busca do Google (www.google.com e www.google.com.br). So mostra o botao
// "Pre Analise SealsPro" acima do painel de um negocio, quando acha o CID dele. Ao clicar (clique de verdade), pede ao
// service worker para abrir o perfil no Maps numa aba nova, onde a captura comeca. Daqui so vao, no clique, os links
// do bloco "Perfis" do painel (redes sociais do perfil, que o Maps nao mostra; CLAUDE.md 13.2 E) e a amostra de
// avaliacoes como a do GBP Check (src/lib/reviews-search.js): os mesmos pedidos que a caixa de avaliacoes da busca faz,
// so depois do clique, com pausa entre eles. E o unico fetch deste content script, e so para esse caminho do Google.
(function () {
  "use strict";
  const { pickCid } = globalThis.__sealsCid;
  const { createSealsProButton, HOST_ID } = globalThis.__sealsButton;
  const reviewsSearch = globalThis.__sealsReviewsSearch;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function panel() {
    return document.querySelector("#rhs .kp-wholepage, #rhs [data-attrid='title'], #rhs") ||
      document.querySelector(".kp-wholepage");
  }

  function cidOf(el) {
    const hrefs = [...el.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"));
    const attrs = [...el.querySelectorAll("[data-ludocid]")].map((n) => n.getAttribute("data-ludocid"));
    return pickCid(hrefs, attrs);
  }

  // Bloco "Perfis" pelo data-attrid (nao depende do idioma). Sem o bloco: lista vazia (o perfil nao tem redes).
  const SOCIAL = '[data-attrid="kc:/common/topic:social media presence"]';
  function socialLinks() {
    const block = document.querySelector(`#rhs ${SOCIAL}`) || document.querySelector(SOCIAL);
    if (!block) return [];
    return [...block.querySelectorAll("a[href]")].map((a) => a.href).filter((h) => /^https?:/i.test(h));
  }

  async function reviewSample(cid) {
    const p = panel();
    const hrefs = p ? [...p.querySelectorAll("a[href]")].map((a) => a.getAttribute("href")) : [];
    const ftid = reviewsSearch.ftidFor(hrefs, cid);
    if (!ftid) return null; // sem o identificador: o app usa a amostra do Maps
    const fetchText = async (path) => {
      const resp = await fetch(location.origin + path, { credentials: "include", cache: "no-store" });
      if (!resp.ok) throw new Error(String(resp.status));
      return resp.text();
    };
    const pages = await reviewsSearch.collect(ftid, fetchText, () => sleep(900 + Math.floor(Math.random() * 700)));
    return pages.lowest.length || pages.newest.length ? pages : null;
  }

  async function onClick(button, cid) {
    button.disabled = true;
    const label = button.textContent;
    try {
      button.textContent = "SealsPro: lendo avaliações…";
      let sample = null;
      try { sample = await reviewSample(cid); } catch (e) { sample = null; }
      button.textContent = label;
      await chrome.runtime.sendMessage({ type: "seals:open-maps", cid, socialLinks: socialLinks(), reviewsSearch: sample });
    } finally {
      button.textContent = label;
      setTimeout(() => { button.disabled = false; }, 3000);
    }
  }

  function mount() {
    const existing = document.getElementById(HOST_ID);
    const p = panel();
    const cid = p && cidOf(p);
    if (!cid) { if (existing) existing.remove(); return; } // sem CID, sem botao
    if (existing && existing.dataset.cid === cid) return;
    if (existing) existing.remove();
    const host = createSealsProButton(document, (button) => onClick(button, cid));
    host.dataset.cid = cid;
    const top = p.closest("#rhs") || p;
    top.insertBefore(host, top.firstChild);
  }

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => { scheduled = false; mount(); }, 500);
  };
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
  schedule();
})();
