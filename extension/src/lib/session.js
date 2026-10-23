// Sessao do content script: recebe as copias do hook (so para o buffer da pagina) e, SO depois do clique no botao
// (mensagem "seals:start" do service worker), roda os passos e entrega a captura ao service worker.
// O content script nunca fala com 127.0.0.1 nem conhece o segredo.
(function (root) {
  "use strict";
  const CAPTURE_KEYS = ["place", "reviews", "reviewsLowest", "photosOwner", "photosVideos", "photos360", "search"];

  function createSession({ buffer, classify, submit, buildSteps, runSteps, now = () => new Date(), getDiagnostics, getExtras }) {
    let running = false;

    function onHookMessage(event, win) {
      if (!event || event.source !== win) return false; // so a propria janela
      const d = event.data;
      if (!d || d.__seals !== 1 || typeof d.text !== "string" || typeof d.url !== "string") return false;
      if (classify(d.url) !== d.kind) return false; // o tipo tem de bater com a URL
      return buffer.add(d.kind, d.text);
    }

    /** Disparado so pela mensagem do clique. Devolve a resposta do service worker, ou um motivo de recusa. */
    async function start(ctx) {
      if (running) return { ok: false, reason: "busy" };
      running = true;
      try {
        const { steps, check } = buildSteps(buffer);
        const problem = check ? check() : null;
        if (problem) return { ok: false, reason: problem };
        const out = await runSteps(steps, ctx);
        if (out.cancelled) return { ok: false, reason: "cancelled" };
        const capture = { capturedAt: now().toISOString() };
        for (const key of CAPTURE_KEYS) capture[key] = key in out.results ? out.results[key] : null;
        capture.extensionErrors = out.errors;
        if (typeof getDiagnostics === "function") capture.diagnostics = getDiagnostics();
        if (typeof getExtras === "function") Object.assign(capture, getExtras());
        return await submit(capture);
      } finally {
        running = false;
      }
    }

    return { onHookMessage, start, isRunning: () => running };
  }

  const api = { createSession, CAPTURE_KEYS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsSession = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
