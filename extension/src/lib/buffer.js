// Buffer da captura passiva: fica so na memoria da pagina (content script ISOLATED), com limite de tamanho, e e
// descartado ao sair da pagina. Nada daqui sai da pagina sem o clique no botao da extensao (ver session.js).
(function (root) {
  "use strict";
  const KINDS = ["place", "reviews", "photos", "search"];

  class CaptureBuffer {
    constructor({ maxBytes = 30 * 1024 * 1024, maxEntries = 400 } = {}) {
      this.maxBytes = maxBytes;
      this.maxEntries = maxEntries;
      this.clear();
    }

    clear() {
      this.entries = [];
      this.bytes = 0;
      this.seq = 0;
      this.overflow = false;
    }

    /** Guarda uma copia; recusa (e marca overflow) se passar dos limites. Devolve true se guardou. */
    add(kind, text) {
      if (!KINDS.includes(kind) || typeof text !== "string") return false;
      if (this.entries.length >= this.maxEntries || this.bytes + text.length > this.maxBytes) {
        this.overflow = true;
        return false;
      }
      this.seq += 1;
      this.entries.push({ seq: this.seq, kind, text });
      this.bytes += text.length;
      return true;
    }

    /** Textos de um tipo guardados depois de `afterSeq` (em ordem). */
    since(afterSeq, kind) {
      return this.entries.filter((e) => e.seq > afterSeq && e.kind === kind).map((e) => e.text);
    }

    latest(kind) {
      for (let i = this.entries.length - 1; i >= 0; i--) if (this.entries[i].kind === kind) return this.entries[i].text;
      return null;
    }
  }

  /** Descarta o buffer quando a pagina e fechada, recarregada ou trocada. */
  function attachLifecycle(target, buffer) {
    const drop = () => buffer.clear();
    target.addEventListener("pagehide", drop);
    target.addEventListener("beforeunload", drop);
    return drop;
  }

  const api = { CaptureBuffer, attachLifecycle, KINDS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsBuffer = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
