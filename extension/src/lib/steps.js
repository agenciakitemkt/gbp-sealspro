// Sequencia dos passos da captura, em ritmo humano. Puro: relogio, sorteio e cancelamento sao injetados.
(function (root) {
  "use strict";
  const PAUSE_MIN = 2000;
  const PAUSE_MAX = 5000;

  function pauseMs(random) {
    return PAUSE_MIN + Math.floor(random() * (PAUSE_MAX - PAUSE_MIN + 1));
  }

  /**
   * Roda os passos em ordem, um de cada vez, com pausa de 2 a 5 s entre eles.
   * Passo que falha (excecao) devolve null para a sua fonte e os demais continuam.
   * steps: [{key, label, run: async () => valor}]
   */
  async function runSteps(steps, { sleep, random = Math.random, isCancelled = () => false, onProgress = () => {} }) {
    const results = {};
    const errors = [];
    let cancelled = false;
    for (let i = 0; i < steps.length; i++) {
      if (isCancelled()) { cancelled = true; break; }
      const step = steps[i];
      onProgress(i + 1, steps.length, step.label);
      try {
        results[step.key] = await step.run();
      } catch (e) {
        results[step.key] = null;
        errors.push({ key: step.key, message: String((e && e.message) || e) });
      }
      if (i < steps.length - 1) await sleep(pauseMs(random));
    }
    return { results, errors, cancelled };
  }

  const api = { runSteps, pauseMs, PAUSE_MIN, PAUSE_MAX };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.__sealsSteps = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
