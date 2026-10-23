// Enderecos das abas controladas. Puro e testado; usado pelo service worker, que valida tudo o que vem do content
// script antes de abrir uma aba.
(function (root) {
  "use strict";
  const CODE = /^[A-Za-z0-9+/_-]{4,40}={0,2}$/;

  /** Leitura minima da fonte A feita na extensao: categoria principal, coordenadas e codigos das categorias da
   *  galeria (so para montar os enderecos; a leitura de verdade fica no app). Null se nao der para ler. */
  function placeInfo(text) {
    try {
      const data = JSON.parse(String(text).replace(/^\)\]\}'\s*/, ""));
      const p = data[6];
      const cats = Array.isArray(p[171] && p[171][0]) ? p[171][0] : [];
      const codes = cats.filter((c) => Array.isArray(c) && typeof c[0] === "string" && CODE.test(c[0])).map((c) => c[0]);
      const info = { category: typeof p[13][0] === "string" ? p[13][0].slice(0, 100) : null,
                     lat: Number(p[9][2]), lng: Number(p[9][3]), codes, ...cityOf(p[2]) };
      return validCoords(info.lat, info.lng) ? info : { ...info, lat: null, lng: null };
    } catch (e) {
      return null;
    }
  }

  function validCoords(lat, lng) {
    return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
  }

  /** Busca da categoria nas coordenadas (como pedido): /maps/search/<categoria>/@lat,lng,13z?hl=pt-BR */
  const STATES = { AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia", CE: "Ceará",
    DF: "Distrito Federal", ES: "Espírito Santo", GO: "Goiás", MA: "Maranhão", MT: "Mato Grosso",
    MS: "Mato Grosso do Sul", MG: "Minas Gerais", PA: "Pará", PB: "Paraíba", PR: "Paraná", PE: "Pernambuco",
    PI: "Piauí", RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RS: "Rio Grande do Sul", RO: "Rondônia",
    RR: "Roraima", SC: "Santa Catarina", SP: "São Paulo", SE: "Sergipe", TO: "Tocantins" };
  const CITY = /^[\p{L}\p{M}][\p{L}\p{M} .'-]{0,59}$/u;

  /** Busca dos concorrentes como no GBP Check: "<categoria> <cidade>-<estado por extenso>" no Maps, zoom 13 perto do
   *  negocio (conferido em 2026-10-10: "Oftalmologista São José dos Campos-São Paulo"). Sem cidade ou estado
   *  reconhecidos: so a categoria. */
  function searchUrl(category, lat, lng, city, uf) {
    if (typeof category !== "string" || !category.trim() || category.length > 100 || !validCoords(lat, lng)) return null;
    const where = typeof city === "string" && CITY.test(city.trim()) && STATES[uf] ? ` ${city.trim()}-${STATES[uf]}` : "";
    const c = encodeURIComponent(category.trim() + where).replace(/%20/g, "+");
    return `https://www.google.com/maps/search/${c}/@${lat.toFixed(7)},${lng.toFixed(7)},13z?hl=pt-BR`;
  }

  /** Cidade e UF da fonte A: o trecho "Cidade - UF" de [6][2] (por exemplo "Belo Horizonte - MG"). */
  function cityOf(lines) {
    for (const line of Array.isArray(lines) ? lines : []) {
      const m = typeof line === "string" && line.match(/^(.+) - ([A-Z]{2})$/);
      if (m && STATES[m[2]]) return { city: m[1].trim(), uf: m[2] };
    }
    return { city: null, uf: null };
  }

  /** Galeria numa categoria, montada do zero a partir do endereco do perfil, no formato conferido numa URL real do
   *  Maps (2026-10-10): <prefixo>!4m9!3m8!1s<ftid>!8m2!3d..!4d..!10e5!14m1!1B<codigo>!16s<id>, com o codigo SEM o "="
   *  final e sem codificar. Montar do zero (e nao remendar o endereco do perfil) evita levar junto o estado de outro
   *  painel: depois do passo das avaliacoes o perfil fica com !9m1!1b1 (avaliacoes abertas), e a aba controlada abria
   *  as avaliacoes no lugar da galeria (achado em 2026-10-10). Null se o perfil nao tiver o formato esperado. */
  function galleryUrl(placeUrl, code) {
    if (typeof placeUrl !== "string" || !CODE.test(String(code))) return null;
    let u;
    try { u = new URL(placeUrl); } catch (e) { return null; }
    if (u.origin !== "https://www.google.com" || !u.pathname.startsWith("/maps/place/")) return null;
    if (u.pathname.includes("!14m1!1B")) return null; // ja e galeria
    const m = u.pathname.match(/^(\/maps\/place\/[^/]+\/(?:@[^/]+\/)?data=)((?:![^!]+)*?)!4m\d+!3m\d+(!1s0x[0-9a-f]+:0x[0-9a-f]+)(!8m2!3d-?[\d.]+!4d-?[\d.]+)/);
    if (!m) return null;
    const id = u.pathname.match(/!16s([^!/?]+)/);
    const bare = encodeURIComponent(String(code).replace(/=+$/, "")); // so + e / seriam codificados
    const inner = `${m[3]}${m[4]}!10e5!14m1!1B${bare}${id ? `!16s${id[1]}` : ""}`;
    const count = 1 + 3 + 1 + 2 + (id ? 1 : 0); // !1s, !8m2 (+3d +4d), !10e5, !14m1 (+1B), !16s
    u.pathname = `${m[1]}${m[2]}!4m${count + 1}!3m${count}${inner}`;
    u.search = "?hl=pt-BR";
    u.hash = "";
    return u.toString();
  }

  const FTID = /^0x[0-9a-f]{1,16}:0x[0-9a-f]{1,16}$/;

  /** Identificador do local (ftid 0x...:0x...) no endereco do perfil aberto (!1s0x...:0x...), ou null. */
  function ftidFromUrl(url) {
    const m = String(url || "").match(/!1s(0x[0-9a-f]{1,16}:0x[0-9a-f]{1,16})/);
    return m ? m[1] : null;
  }

  /** Identificador do local numa resposta preview/place ([6][10]), ou null. */
  function ftidFromPlace(text) {
    try {
      const v = JSON.parse(String(text).replace(/^\)\]\}'\s*/, ""))[6][10];
      return typeof v === "string" && FTID.test(v) ? v : null;
    } catch (e) {
      return null;
    }
  }

  /** A resposta preview/place mais recente que e do perfil aberto (o Maps tambem busca outros locais do mapa). */
  function placeForProfile(texts, url) {
    const want = ftidFromUrl(url);
    if (!want) return null;
    for (let i = texts.length - 1; i >= 0; i--) if (ftidFromPlace(texts[i]) === want) return texts[i];
    return null;
  }

  /** Categoria de uma pagina da galeria (hspqX): o codigo em [13][0] do JSON interno. As paginas do visualizador do
   *  Street View (panoramas vizinhos, mesmo hspqX) nao tem [13]: null. So para a aba controlada esperar a pagina certa. */
  function galleryInner(text) {
    try {
      for (const line of String(text).split("\n")) {
        if (!line.includes('"wrb.fr"')) continue;
        const inner = JSON.parse(JSON.parse(line)[0][2]);
        return Array.isArray(inner) ? inner : null;
      }
    } catch (e) { /* formato inesperado */ }
    return null;
  }

  function galleryCategory(text) {
    const inner = galleryInner(text);
    const code = inner && Array.isArray(inner[13]) ? inner[13][0] : null;
    return typeof code === "string" ? code : null;
  }

  /** A pagina marca o fim da categoria: true em [10] (o mesmo sinal que o leitor do app usa). Para de rolar. */
  function galleryEnd(text) {
    const inner = galleryInner(text);
    return !!inner && inner[10] === true;
  }

  const api = { galleryCategory, galleryEnd, placeInfo, searchUrl, galleryUrl, validCoords, ftidFromUrl, ftidFromPlace, placeForProfile };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsUrls = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
