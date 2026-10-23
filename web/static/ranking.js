// Mapa da Analise de Ranking: um marcador por ponto da grade com a posicao do local escolhido na lista.
// Nomes vindos do Maps sao nao confiaveis: entram so por textContent; o marcador so recebe numeros.
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("rk-data").textContent);
  var map = L.map("rk-map", { scrollWheelZoom: false });
  // Fundo do OpenStreetMap (uso leve, com atribuicao). O Carto passou a pedir chave (2026-10-11).
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>",
  }).addTo(map);

  var unread = {}, off = {}, editing = false, pending = {};
  data.unread.forEach(function (i) { unread[i] = true; });
  (data.disabled || []).forEach(function (i) { off[i] = true; });
  var layer = L.layerGroup().addTo(map);
  var current = 0;
  var pin = data.size >= 13 ? 26 : data.size >= 11 ? 30 : 34; // circulos menores nas grades grandes

  function isOff(i) { return editing ? !!pending[i] : !!off[i]; }

  function cls(i, p) {
    if (isOff(i)) return "rk-off";
    if (unread[i]) return "rk-p0";
    if (p === null) return "rk-p4";
    return p <= 3 ? "rk-p1" : p <= 10 ? "rk-p2" : "rk-p3";
  }

  function draw(k) {
    current = k;
    layer.clearLayers();
    var positions = data.series[k];
    data.points.forEach(function (pt, i) {
      var p = positions[i];
      var text = isOff(i) ? "\u00d7" : unread[i] ? "?" : p === null ? "20+" : String(p);
      var icon = L.divIcon({ className: "rk-pin " + cls(i, p) + (editing ? " rk-editing" : "") + (pin < 34 ? " rk-pin-sm" : ""),
                             html: text, iconSize: [pin, pin] });
      var marker = L.marker([pt.lat, pt.lng], { icon: icon, keyboard: false }).addTo(layer);
      marker.on("click", function () {
        if (!editing) return;
        if (pending[i]) delete pending[i]; else pending[i] = true;
        draw(current);
      });
    });
    document.getElementById("rk-map-title").textContent = data.names[k] || data.own;
    document.querySelectorAll(".rk-comp").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.k === String(k) ? "true" : "false");
    });
  }

  var own = document.querySelector(".rk-comp.rk-own");
  var start = own ? Number(own.dataset.k) : -1;
  if (start < 0) { // o perfil nao apareceu em nenhum ponto: grade toda "20+"
    data.series.push(data.points.map(function () { return null; }));
    data.names.push(data.own);
    start = data.series.length - 1;
  }
  map.fitBounds(L.latLngBounds(data.points.map(function (p) { return [p.lat, p.lng]; })).pad(0.15));
  L.circleMarker(data.center, { radius: 5, color: "#0B0B0D", weight: 2, fillColor: "#818CF8", fillOpacity: 1 })
    .addTo(map);
  draw(start);
  document.querySelectorAll(".rk-comp").forEach(function (b) {
    b.addEventListener("click", function () { draw(Number(b.dataset.k)); });
  });

  // ---- desligar pontos (represa, mata...): clica no ponto, salva; o app recalcula e guarda para as proximas ----
  var editBtn = document.getElementById("rk-edit");
  if (!editBtn) return;
  var save = document.getElementById("rk-edit-save"), cancel = document.getElementById("rk-edit-cancel");
  var msg = document.getElementById("rk-edit-msg"), helpText = msg.textContent;
  function setEditing(on) {
    editing = on;
    pending = {};
    if (on) Object.keys(off).forEach(function (i) { pending[i] = true; });
    editBtn.hidden = on; save.hidden = !on; cancel.hidden = !on;
    msg.textContent = on ? "Clique nos pontos para desligar (×) ou religar e depois em Salvar." : helpText;
    draw(current);
  }
  editBtn.addEventListener("click", function () { setEditing(true); });
  cancel.addEventListener("click", function () { setEditing(false); });
  save.addEventListener("click", function () {
    var list = Object.keys(pending).map(Number);
    save.disabled = true;
    fetch("/ranking/pontos?id=" + encodeURIComponent(data.id), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ disabled: list }),
    }).then(function (r) { return r.json(); }).then(function (r) {
      if (r.ok) { location.reload(); return; }
      save.disabled = false;
      msg.textContent = "Não foi possível: " + (r.error || "erro");
    }).catch(function () { save.disabled = false; msg.textContent = "Não foi possível salvar agora."; });
  });
})();
