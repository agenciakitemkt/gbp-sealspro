// CID do negocio a partir dos links e atributos do painel da busca do Google. So leitura; nada e enviado daqui.
// Fontes, em ordem de confianca: ludocid=, data-ludocid, cid= (links do Maps), e o ftid 0x...:0x<hex> dos links
// do Maps (hexadecimal convertido para decimal). Fica o CID que mais aparece (o do proprio negocio se repete nos
// links do painel; o de outro negocio aparece uma vez). Sem CID valido: null (e o botao nao aparece).
(function (root) {
  "use strict";
  const DIGITS = /^\d{5,25}$/;

  function fromHref(href) {
    if (typeof href !== "string" || !href) return [];
    const out = [];
    let decoded = href;
    try { decoded = decodeURIComponent(href); } catch (e) { /* mantem como veio */ }
    for (const re of [/[?&]ludocid=(\d{5,25})(?:&|$|#)/g, /[?&]cid=(\d{5,25})(?:&|$|#)/g]) {
      for (const m of decoded.matchAll(re)) out.push(m[1]);
    }
    for (const m of decoded.matchAll(/0x[0-9a-f]{1,16}:0x([0-9a-f]{1,16})/gi)) {
      try { out.push(BigInt("0x" + m[1]).toString()); } catch (e) { /* ignora */ }
    }
    return out.filter((c) => DIGITS.test(c) && c !== "0");
  }

  /** hrefs: links do painel; attrs: valores de data-ludocid. Devolve o CID mais frequente ou null. */
  function pickCid(hrefs, attrs = []) {
    const counts = new Map();
    const order = [];
    const add = (cid, weight) => {
      if (!counts.has(cid)) order.push(cid);
      counts.set(cid, (counts.get(cid) || 0) + weight);
    };
    for (const a of attrs) if (DIGITS.test(String(a))) add(String(a), 2);
    for (const h of hrefs) for (const cid of fromHref(h)) add(cid, 1);
    let best = null;
    for (const cid of order) if (best === null || counts.get(cid) > counts.get(best)) best = cid;
    return best;
  }

  function mapsUrl(cid) {
    if (!DIGITS.test(String(cid))) return null;
    return `https://www.google.com/maps?cid=${cid}&hl=pt-BR`;
  }

  const api = { pickCid, fromHref, mapsUrl };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsCid = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
