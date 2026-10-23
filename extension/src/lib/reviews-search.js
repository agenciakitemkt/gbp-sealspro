// Amostra de avaliacoes como a do GBP Check (comparacao ao vivo, 2026-10-10): a caixa de avaliacoes da busca do
// Google, em hl=en-BR, lista "menor nota" + lista "mais recentes", ate 5 paginas (50 avaliacoes) cada, sem repetir.
// Conferido em 3 perfis de terceiros: tamanho, media, com comentario e sem resposta iguais aos do GBP Check.
// A extensao faz os mesmos pedidos GET que a propria caixa faz (GetLocalBoqProxy), na pagina da busca, so depois do
// clique no botao, com pausa entre eles. Nada e interpretado aqui: as paginas vao em texto para o app.
(function (root) {
  "use strict";
  const PATH = "/httpservice/web/PrivateLocalSearchUiDataService/GetLocalBoqProxy";
  const SORT = { lowest: 4, newest: 2 };
  // Menor nota: 5 paginas. Mais recentes: ate 13 (130 avaliacoes), porque com ate cerca de 130 avaliacoes o GBP Check
  // le todas; acima disso o app usa so as 5 primeiras de cada lista (collector_pre/maps_reader.py).
  const MAX_PAGES = { lowest: 5, newest: 13 };
  const FTID = /^0x[0-9a-f]{1,16}:0x[0-9a-f]{1,16}$/;

  /** Pedido de uma pagina, no formato que a caixa usa (10 por pagina; token = proxima pagina). */
  function pageUrl(ftid, sort, token) {
    if (!FTID.test(String(ftid)) || !Object.values(SORT).includes(sort)) return null;
    if (token !== null && (typeof token !== "string" || !/^[A-Za-z0-9_-]{1,200}$/.test(token))) return null;
    const pld = [null, [null, null, null, null, null, null, null, null, null,
      [null, sort, null, null, null, null, null, null, null, 10, null, [ftid], null, null, null, null,
        [1, 1, null, [[3], [4], [5], [6], [7]]], null, null, token, null, null, null, 0]]];
    return `${PATH}?hl=en-BR&reqpld=${encodeURIComponent(JSON.stringify(pld))}&msc=gwsrpc&opi=89978449`;
  }

  /** Token da proxima pagina ([1][10][6]); "" ou ausente = fim. So leitura minima, para paginar. */
  function nextToken(text) {
    try {
      const s = String(text);
      const data = JSON.parse(s.slice(s.indexOf("\n") + 1));
      const token = data[1][10][6];
      return typeof token === "string" && token ? token : null;
    } catch (e) {
      return null;
    }
  }

  /** ftid do negocio (0x...:0x<hex do CID>) a partir dos links do painel, conferindo com o CID. */
  function ftidFor(hrefs, cid) {
    for (const href of hrefs) {
      let text = String(href || "");
      try { text = decodeURIComponent(text); } catch (e) { /* mantem */ }
      for (const m of text.matchAll(/0x[0-9a-f]{1,16}:0x([0-9a-f]{1,16})/gi)) {
        try { if (BigInt("0x" + m[1]).toString() === String(cid)) return m[0].toLowerCase(); } catch (e) { /* ignora */ }
      }
    }
    return null;
  }

  /** As duas listas (ate MAX_PAGES paginas cada). fetchText(url) devolve o texto ou lanca; pause() espera entre pedidos.
   *  Devolve { lowest: [textos], newest: [textos] } (uma lista que falhou volta com o que chegou). */
  async function collect(ftid, fetchText, pause) {
    const out = { lowest: [], newest: [] };
    for (const key of ["lowest", "newest"]) {
      let token = null;
      for (let i = 0; i < MAX_PAGES[key]; i++) {
        const url = pageUrl(ftid, SORT[key], token);
        if (!url) break;
        await pause();
        let text;
        try { text = await fetchText(url); } catch (e) { break; }
        if (typeof text !== "string" || !text.startsWith(")]}'")) break;
        out[key].push(text);
        token = nextToken(text);
        if (!token) break;
      }
    }
    return out;
  }

  const api = { pageUrl, nextToken, ftidFor, collect, PATH, SORT, MAX_PAGES };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsReviewsSearch = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
