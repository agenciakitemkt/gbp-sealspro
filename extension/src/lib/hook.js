// Mundo MAIN: copia (sem alterar) as respostas que match.classify reconhece e entrega a `emit`.
// Nao conhece o segredo nem o app local: so repassa para o content script da propria pagina.
(function (root) {
  "use strict";
  const MAX_TEXT = 8 * 1024 * 1024; // resposta maior que isso e ignorada

  /** Rastro para diagnostico: so o caminho e o rpcids do pedido, nunca parametros com dados nem o corpo. */
  function traceOf(url, base) {
    try {
      const u = new URL(url, base);
      if (u.hostname !== "www.google.com") return null;
      const rpc = u.searchParams.get("rpcids");
      const tbm = u.searchParams.get("tbm");
      return u.pathname.slice(0, 80) + (rpc ? `?rpcids=${rpc.slice(0, 40)}` : "") + (tbm ? `?tbm=${tbm.slice(0, 10)}` : "");
    } catch (e) {
      return null;
    }
  }

  function installHook(win, classify, emit, trace = () => {}) {
    if (!win || win.__sealsHooked) return false;
    win.__sealsHooked = true;
    const base = () => (win.location && win.location.href) || "https://www.google.com/";
    // Para o diagnostico, o rastro tambem diz se cada resposta reconhecida foi entregue (so tipo e tamanho).
    const deliver = (kind, url, text, how) => {
      if (typeof text !== "string") { trace(`<= ${kind} ${how}: sem texto (${typeof text})`); return; }
      if (text.length > MAX_TEXT) { trace(`<= ${kind} ${how}: grande demais (${text.length})`); return; }
      trace(`<= ${kind} ${how}: ${text.length} caracteres`);
      emit({ kind, url, text });
    };

    if (typeof win.fetch === "function") {
      const original = win.fetch;
      win.fetch = function (input, init) {
        const url = typeof input === "string" ? input : (input && input.url) || "";
        const promise = original.apply(this, arguments);
        const kind = classify(url, base());
        const t = traceOf(url, base());
        if (t) trace(`${t} [fetch]`);
        if (kind) {
          promise.then((resp) => resp.clone().text()).then((t) => deliver(kind, url, t, "fetch"))
            .catch((e) => trace(`<= ${kind} fetch: falhou (${String(e && e.name)})`));
        }
        return promise;
      };
    }

    const XHR = win.XMLHttpRequest;
    if (XHR && XHR.prototype) {
      const open = XHR.prototype.open;
      const send = XHR.prototype.send;
      XHR.prototype.open = function (method, url) {
        this.__sealsUrl = String(url || "");
        return open.apply(this, arguments);
      };
      XHR.prototype.send = function () {
        const kind = classify(this.__sealsUrl || "", base());
        const t = traceOf(this.__sealsUrl || "", base());
        if (t) trace(`${t} [xhr]`);
        if (kind) {
          // Entrega uma vez so, no primeiro sinal de fim: readyState 4, load ou loadend (a biblioteca do Google
          // pode concluir o pedido sem que o "load" chegue ao nosso ouvinte).
          // A busca do Maps (paginas 2 em diante) vem em partes e o pedido fica aberto: entrega assim que o texto ja
          // recebido forma um JSON completo (sem o prefixo )]}'), sem esperar o fim do pedido. So tenta quando o texto
          // cresceu e termina em "]" (a pagina 1 termina em "]]]]").
          let done = false;
          let lastLength = 0;
          const complete = () => {
            let text;
            try { text = this.responseText; } catch (e) { return false; }
            if (typeof text !== "string" || text.length === lastLength) return false;
            lastLength = text.length;
            const body = text.replace(/^\)\]\}'\s*/, "").replace(/\/\*""\*\/\s*$/, "").trimEnd();
            if (!body.endsWith("]")) return false;
            try { JSON.parse(body); return true; } catch (e) { return false; }
          };
          const finish = (how) => {
            if (done) return;
            if (!(this.readyState === 4 || (this.readyState === 3 && kind === "search" && complete()))) return;
            done = true;
            try {
              if (this.responseType === "" || this.responseType === "text") deliver(kind, this.__sealsUrl, this.responseText, `xhr/${how}`);
              else trace(`<= ${kind} xhr: responseType=${this.responseType}`);
            } catch (e) { trace(`<= ${kind} xhr: ilegivel (${String(e && e.name)})`); }
          };
          this.addEventListener("readystatechange", () => finish(this.readyState === 3 ? "parcial" : "rs4"));
          this.addEventListener("progress", () => finish("parcial"));
          this.addEventListener("load", () => finish("load"));
          this.addEventListener("loadend", () => { finish("loadend"); if (!done) trace(`<= ${kind} xhr: terminou sem resposta (status ${this.status})`); });
          this.addEventListener("abort", () => trace(`<= ${kind} xhr: abortado`));
        }
        return send.apply(this, arguments);
      };
    }
    return true;
  }

  const api = { installHook, traceOf, MAX_TEXT };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsHook = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
