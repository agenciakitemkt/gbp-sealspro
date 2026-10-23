// Formulario de postagem: contador, pre-visualizacao ao vivo e envio da imagem (o arquivo vai sozinho, como corpo do
// pedido, para /postagens/imagem; o app confere, regrava como JPEG e devolve um token). Sem innerHTML: so textContent.
(function () {
  "use strict";
  var form = document.getElementById("pt-form");
  if (!form) return;
  var max = parseInt(form.dataset.max, 10);
  var semLink = (form.dataset.semLink || "").split(",");
  var $ = function (id) { return document.getElementById(id); };
  var texto = $("pt-texto"), count = $("pt-count"), botao = $("pt-botao"), url = $("pt-url"),
      urlWrap = $("pt-url-wrap"), callHint = $("pt-call-hint"), data = $("pt-data"), salvar = $("pt-salvar"),
      arquivo = $("pt-arquivo"), imagem = $("pt-imagem"), remover = $("pt-remover"), imgStatus = $("pt-img-status"),
      upload = form.querySelector(".pt-upload"),
      pvTexto = $("pv-texto"), pvBotao = $("pv-botao"), pvData = $("pv-data"), pvImg = $("pv-img"),
      pvImgWrap = $("pv-img-wrap");

  function onText() {
    count.textContent = texto.value.length + "/" + max + " caracteres";
    count.classList.toggle("pt-over", texto.value.length > max);
    pvTexto.textContent = texto.value || "O texto da postagem aparece aqui.";
  }

  function onButton() {
    var value = botao.value;
    var needsUrl = semLink.indexOf(value) === -1;
    urlWrap.hidden = !needsUrl;
    url.required = needsUrl;
    callHint.hidden = value !== "CALL";
    pvBotao.hidden = !value;
    pvBotao.textContent = botao.options[botao.selectedIndex].text;
  }

  function quando() {
    var checked = form.querySelector('input[name="quando"]:checked');
    return checked ? checked.value : "agendar";
  }

  function onWhen() {
    var agora = quando() === "agora";
    data.disabled = agora;
    data.required = !agora;
    salvar.textContent = agora ? "Publicar agora" : "Salvar agendamento";
    var d = agora ? new Date() : (data.value ? new Date(data.value) : null);
    pvData.textContent = d && !isNaN(d) ? d.toLocaleDateString("pt-BR") : "";
  }

  function showImage(token) {
    imagem.value = token || "";
    pvImgWrap.hidden = !token;
    if (token) pvImg.src = "/postagens/imagem/" + token;
    else pvImg.removeAttribute("src");
    remover.hidden = !token;
    upload.textContent = token ? "Trocar imagem" : "Escolher imagem";
  }

  arquivo.addEventListener("change", function () {
    var file = arquivo.files && arquivo.files[0];
    if (!file) return;
    imgStatus.textContent = "Enviando…";
    salvar.disabled = true;
    fetch("/postagens/imagem", { method: "POST", body: file, headers: { "Content-Type": file.type || "application/octet-stream" } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j.erro || "Não foi possível enviar a imagem.");
        showImage(res.j.token);
        imgStatus.textContent = "Imagem pronta (" + res.j.width + "×" + res.j.height + ").";
      })
      .catch(function (e) { imgStatus.textContent = e.message || "Não foi possível enviar a imagem."; })
      .then(function () { salvar.disabled = false; arquivo.value = ""; });
  });

  remover.addEventListener("click", function () { showImage(""); imgStatus.textContent = "Imagem removida."; });
  texto.addEventListener("input", onText);
  botao.addEventListener("change", onButton);
  data.addEventListener("input", onWhen);
  form.querySelectorAll('input[name="quando"]').forEach(function (r) { r.addEventListener("change", onWhen); });
  form.addEventListener("submit", function (e) {
    if (quando() === "agora" && !window.confirm("Publicar agora no perfil do Google?")) e.preventDefault();
  });
  onText(); onButton(); onWhen();
})();
