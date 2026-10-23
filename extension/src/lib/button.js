// Botao "Pre Analise SealsPro" dentro da pagina: num shadow DOM fechado (a pagina nao alcanca o botao) e so reage a
// clique de verdade (event.isTrusted). Pequeno, em linha (nao cobre nada) e ao lado do que ja estiver ali.
(function (root) {
  "use strict";
  const HOST_ID = "seals-pre-analise";
  const LABEL = "Pré Análise SealsPro";
  const RANKING = { id: "seals-ranking", label: "Ranking SealsPro" };
  const CSS = [
    ":host{all:initial;display:block;margin:8px 0}",
    "button{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:6px;cursor:pointer;",
    "font:600 13px/1 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#0B0B0D;background:#14B8A6;",
    "padding:7px 12px;border-radius:16px;border:1px solid #1a9e4b}",
    "button:hover{background:#1fb455}button:focus-visible{outline:2px solid #818CF8;outline-offset:2px}",
    "button[disabled]{opacity:.6;cursor:default}",
  ].join("");

  /** Chama `handler` so para eventos gerados pelo usuario (nao por script da pagina). */
  function guardTrusted(handler) {
    return (event) => {
      if (!event || event.isTrusted !== true) return false;
      if (typeof event.preventDefault === "function") event.preventDefault();
      if (typeof event.stopPropagation === "function") event.stopPropagation();
      handler(event);
      return true;
    };
  }

  /** opts: {id, label} para outro botao (o "Ranking SealsPro"); sem opts, o "Pre Analise SealsPro". */
  function createSealsProButton(doc, onTrustedClick, { id = HOST_ID, label = LABEL } = {}) {
    const host = doc.createElement("div");
    host.id = id;
    const shadow = host.attachShadow({ mode: "closed" });
    const style = doc.createElement("style");
    style.textContent = CSS;
    const button = doc.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-label", label);
    button.addEventListener("click", guardTrusted(() => onTrustedClick(button)));
    shadow.append(style, button);
    return host;
  }

  const api = { createSealsProButton, guardTrusted, HOST_ID, LABEL, RANKING };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsButton = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
