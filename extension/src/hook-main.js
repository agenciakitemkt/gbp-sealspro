// Entrada do mundo MAIN (document_start): instala o hook e entrega as copias ao content script por postMessage.
// A pagina tambem ve essas mensagens, mas elas so tem o que a propria pagina ja recebeu do Google.
(function () {
  "use strict";
  const { classify } = globalThis.__sealsMatch;
  globalThis.__sealsHook.installHook(window, classify, (msg) => {
    window.postMessage({ __seals: 1, kind: msg.kind, url: msg.url, text: msg.text }, window.location.origin);
  }, (path) => {
    window.postMessage({ __seals: 1, trace: path }, window.location.origin);
  });
})();
