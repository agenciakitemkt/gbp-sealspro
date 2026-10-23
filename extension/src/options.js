// Pagina de opcoes: grava o segredo em chrome.storage.local (nunca em sync) e testa a conexao pelo service worker.
const $ = (id) => document.getElementById(id);
$("ext-id").textContent = chrome.runtime.id;
chrome.storage.local.get("sealsSecret").then(({ sealsSecret }) => {
  $("status").textContent = sealsSecret ? "Segredo já configurado." : "Segredo ainda não configurado.";
});
$("save").addEventListener("click", async () => {
  const value = $("secret").value.trim();
  if (value.length < 32) { $("status").textContent = "O segredo tem pelo menos 32 caracteres."; return; }
  await chrome.storage.local.set({ sealsSecret: value });
  $("secret").value = "";
  $("status").textContent = "Segredo salvo.";
});
$("test").addEventListener("click", async () => {
  $("status").textContent = "Testando…";
  const r = await chrome.runtime.sendMessage({ type: "seals:ping" });
  $("status").textContent = r && r.ok ? "Conexão ok: o app reconheceu a extensão e o segredo."
    : r && r.status === 403 ? "O app recusou: confira o ID (coletar.py id-extensao) e o segredo."
    : "Sem resposta do app: ele está rodando em http://127.0.0.1:8000?";
});
