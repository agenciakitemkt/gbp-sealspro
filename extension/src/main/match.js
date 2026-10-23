// Quais respostas do Google Maps a extensao copia (CLAUDE.md, 13.2). Nada mais e lido.
// Usado no mundo MAIN (hook) e no ISOLATED (relay). Sem acesso a chrome.*, sem segredo.
// Ha uma copia IDENTICA em src/main/match.js, usada pelo mundo MAIN: o Chrome injeta um mesmo arquivo uma unica vez
// por pagina, entao, listado nas duas entradas do manifest, ele so rodava num dos mundos. Um teste confere a copia.
(function (root) {
  "use strict";
  const ALLOWED_HOST = /^www\.google\.com$/;

  function classify(url, base) {
    let u;
    try {
      u = new URL(url, base || "https://www.google.com/");
    } catch (e) {
      return null;
    }
    if (u.protocol !== "https:" || !ALLOWED_HOST.test(u.hostname)) return null;
    const path = u.pathname;
    if (path.startsWith("/maps/preview/place")) return "place";
    if (path.endsWith("/batchexecute")) {
      const rpc = u.searchParams.get("rpcids") || "";
      if (rpc.split(",").includes("qv9Egd")) return "reviews";
      if (rpc.split(",").includes("hspqX")) return "photos";
      return null;
    }
    if (path === "/search" && u.searchParams.get("tbm") === "map") return "search";
    return null;
  }

  const api = { classify };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsMatch = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
