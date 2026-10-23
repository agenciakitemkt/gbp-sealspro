// Busca de Leads (CLAUDE.md, secao 18): filtros, ordem, cartoes, tabela, mapa, notas, favoritos e planilha.
// Todo texto vem do Google Maps e nao e confiavel: so textContent (nunca HTML montado com texto), e link so vira href se for
// http(s) ou montado aqui a partir do CID/place_id.
(function () {
  "use strict";
  const data = JSON.parse(document.getElementById("ld-data").textContent);
  const leads = data.leads;
  const notes = data.notes || {};
  const favorites = new Set(data.favorites || []);
  const pre = data.pre || {};
  const PAGE = 60;
  const BANDS = { fair: 60, good: 80 }; // faixas do medidor (scoring/config.py, OVERALL_BANDS)
  const STOP = new Set(["de", "da", "do", "das", "dos", "e", "em", "the", "and", "com", "para", "por", "ltda", "me",
                        "eireli", "sa", "s/a", "na", "no", "a", "o", "um", "uma"]);
  const state = { sort: "quality", asc: true, view: "cards", limit: PAGE, q: "" };
  let map = null, layer = null;

  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs, ...children) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children) if (c !== null && c !== undefined && c !== false) e.append(c);
    return e;
  };
  const safeHref = (u) => (typeof u === "string" && /^https?:\/\//i.test(u) ? u : null);
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const num = (id) => { const v = $(id) && $(id).value.trim().replace(",", "."); return v === "" || v === undefined ? null : Number(v); };
  const fmt = (n, d = 1) => (n === null || n === undefined ? "–" : Number(n).toLocaleString("pt-BR", { maximumFractionDigits: d }));
  const band = (score) => (score === null || score === undefined ? "unavailable" : score >= BANDS.good ? "good" : score >= BANDS.fair ? "fair" : "bad");
  const siteKind = (l) => { const it = (l.quality.items || []).find((i) => i.id === "website"); return !l.website ? "no" : it && it.score === 50 ? "social" : "own"; };

  function mapsUrl(l) {
    if (l.cid && /^\d{1,25}$/.test(l.cid)) return `https://www.google.com/maps?cid=${l.cid}`;
    if (l.placeId) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(l.name)}&query_place_id=${encodeURIComponent(l.placeId)}`;
    return null;
  }
  // Pre Analise do lead: o painel do negocio na busca do Google, onde fica o botao "Pre Analise SealsPro" da extensao.
  const preUrl = (l) => (l.cid && /^\d{1,25}$/.test(l.cid) ? `https://local.google.com/place?id=${l.cid}` : null);
  function whatsapp(phone) {
    const d = String(phone || "").replace(/\D/g, "").replace(/^55(?=\d{10,11}$)/, "");
    return d.length === 11 && d[2] === "9" ? `https://wa.me/55${d}` : null; // so celular (DDD + 9 digitos)
  }

  // ---------------- filtros ----------------
  function radio(name) { const r = document.querySelector(`input[name="${name}"]:checked`); return r ? r.value : ""; }
  const checked = (id) => !!($(id) && $(id).checked);

  function matches(l) {
    const phone = radio("phone"), site = radio("site"), verified = radio("verified"), sab = radio("sab");
    if (phone === "yes" && !l.phone) return false;
    if (phone === "no" && l.phone) return false;
    if (site && siteKind(l) !== site) return false;
    if (verified === "yes" && !l.verified) return false;
    if (verified === "no" && l.verified) return false;
    if (sab === "yes" && !l.sab) return false;
    if (sab === "no" && l.sab) return false;
    if (checked("ld-inside") && l.inside === false) return false;
    if (checked("ld-hours") && l.hours && Object.keys(l.hours).length) return false;
    if (checked("ld-multicat") && (l.categories || []).length < 2) return false;
    if (checked("ld-noted") && !notes[l.key]) return false;
    if (checked("ld-fav") && !favorites.has(l.key)) return false;
    if (checked("ld-pre") && !pre[l.cid]) return false;
    const r = l.rating, c = l.reviews, q = l.quality.score;
    const rmin = num("ld-rmin"), rmax = num("ld-rmax"), cmin = num("ld-cmin"), cmax = num("ld-cmax");
    const qmin = num("ld-qmin"), qmax = num("ld-qmax");
    if (rmin !== null && !(r !== null && r >= rmin)) return false;
    if (rmax !== null && !((r || 0) <= rmax)) return false;
    if (cmin !== null && !(c !== null && c >= cmin)) return false;
    if (cmax !== null && !((c || 0) <= cmax)) return false;
    if (qmin !== null && !((q || 0) >= qmin)) return false;
    if (qmax !== null && !((q || 0) <= qmax)) return false;
    if (state.q) {
      const hay = norm([l.name, (l.categories || []).join(" "), l.address, l.phone, l.website, notes[l.key]].join(" "));
      if (!norm(state.q).split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  }

  function sorted(list) {
    const key = { quality: (l) => l.quality.score, rating: (l) => l.rating, reviews: (l) => l.reviews,
                  name: (l) => norm(l.name), order: (l) => l.order }[state.sort];
    const dir = state.asc ? 1 : -1;
    return list.slice().sort((a, b) => {
      const x = key(a), y = key(b);
      if (x === y) return a.order - b.order;
      if (x === null || x === undefined) return 1; // sem dado sempre no fim
      if (y === null || y === undefined) return -1;
      return (x < y ? -1 : 1) * dir;
    });
  }

  function current() { return sorted(leads.filter(matches)); }

  // ---------------- cartoes ----------------
  function stars(rating) {
    if (rating === null || rating === undefined) return "";
    const full = Math.round(rating);
    return "★".repeat(full) + "☆".repeat(5 - full);
  }

  function favButton(l) {
    const on = favorites.has(l.key);
    const b = el("button", { type: "button", class: "ld-fav" + (on ? " on" : ""), "aria-pressed": on ? "true" : "false",
                             title: on ? "Tirar dos favoritos" : "Marcar como favorito", text: on ? "★" : "☆" });
    b.addEventListener("click", async () => {
      const want = !favorites.has(l.key);
      b.disabled = true;
      const ok = await post("/leads/favorito", { key: l.key, search: data.search, on: want });
      b.disabled = false;
      if (!ok) { alert("Não foi possível salvar o favorito."); return; }
      if (want) favorites.add(l.key); else favorites.delete(l.key);
      b.classList.toggle("on", want); b.textContent = want ? "★" : "☆";
      b.setAttribute("aria-pressed", want ? "true" : "false");
      b.title = want ? "Tirar dos favoritos" : "Marcar como favorito";
    });
    return b;
  }

  function notesBox(l) {
    const box = el("details", { class: "ld-notes" }, el("summary", { text: notes[l.key] ? "Nota da SealsPro: " + notes[l.key].split("\n")[0].slice(0, 60) : "Adicionar nota" }));
    const area = el("textarea", { rows: "3", maxlength: "2000", "aria-label": "Nota sobre " + l.name });
    area.value = notes[l.key] || "";
    const msg = el("span", { class: "muted small", role: "status" });
    const save = el("button", { type: "button", class: "btn btn-secondary", text: "Salvar nota" });
    save.addEventListener("click", async () => {
      save.disabled = true;
      const ok = await post("/leads/nota", { key: l.key, note: area.value });
      save.disabled = false;
      if (!ok) { msg.textContent = "Não foi possível salvar."; return; }
      if (area.value.trim()) notes[l.key] = area.value.trim(); else delete notes[l.key];
      box.querySelector("summary").textContent = notes[l.key] ? "Nota da SealsPro: " + notes[l.key].split("\n")[0].slice(0, 60) : "Adicionar nota";
      msg.textContent = "Salva.";
    });
    box.append(area, el("div", { class: "ld-note-actions" }, save, msg));
    return box;
  }

  function qualityBlock(l) {
    const q = l.quality, b = band(q.score);
    const chips = el("ul", { class: "ld-chips" });
    for (const it of q.items) {
      chips.append(el("li", { class: `badge st-${it.status}`, title: it.status === "unavailable" ? "A busca não trouxe este dado" : "" , text: it.title }));
    }
    return el("div", { class: "ld-quality" },
      el("div", { class: "ld-qhead" }, el("span", { text: "Qualidade estimada" }), el("strong", { class: `ld-qnum st-${b}`, text: q.score === null ? "–" : String(q.score) })),
      el("div", { class: "ld-qbar", role: "img", "aria-label": `Qualidade ${q.score} de 100` }, el("span", { class: `ld-qfill band-${b}`, style: `width:${q.score || 0}%` })),
      chips);
  }

  function row(label, value, href) {
    const v = href ? el("a", { href, target: "_blank", rel: "noopener noreferrer", text: value }) : el("span", { text: value });
    return el("div", { class: "ld-row" }, el("dt", { text: label }), el("dd", {}, v));
  }

  function card(l) {
    const site = safeHref(l.website);
    const kind = siteKind(l);
    const facts = el("dl", { class: "ld-facts" });
    const phoneDd = el("dd", {});
    if (l.phone) {
      phoneDd.append(el("a", { href: "tel:" + l.phone.replace(/[^\d+]/g, ""), text: l.phone }));
      const wa = whatsapp(l.phone);
      if (wa) phoneDd.append(" · ", el("a", { href: wa, target: "_blank", rel: "noopener noreferrer", text: "WhatsApp" }));
    } else phoneDd.append(el("span", { class: "ld-missing", text: "Não tem" }));
    facts.append(el("div", { class: "ld-row" }, el("dt", { text: "Telefone" }), phoneDd));
    const siteDd = el("dd", {});
    if (l.website) {
      siteDd.append(site ? el("a", { href: site, target: "_blank", rel: "noopener noreferrer", text: l.website.replace(/^https?:\/\/(www\.)?/i, "").slice(0, 60) }) : el("span", { text: l.website.slice(0, 60) }));
      if (kind === "social") siteDd.append(" ", el("span", { class: "badge st-fair", text: "rede social" }));
    } else siteDd.append(el("span", { class: "ld-missing", text: "Não tem" }));
    facts.append(el("div", { class: "ld-row" }, el("dt", { text: "Site" }), siteDd));
    facts.append(row("Endereço", l.sab ? "Sem endereço (atende por área)" : l.address || "–"));
    if (l.inside === false) facts.append(row("Região", "Fora da região buscada"));
    facts.append(row("Horário", l.hours && Object.keys(l.hours).length ? "Definido" : "Não definido"));

    const ratingLine = el("p", { class: "ld-rating" });
    if (l.rating !== null && l.rating !== undefined) {
      ratingLine.append(el("strong", { text: fmt(l.rating) }), " ", el("span", { class: "stars", "aria-hidden": "true", text: stars(l.rating) }),
        " ", el("span", { class: "muted", text: l.reviews === null || l.reviews === undefined ? "(quantidade não informada)" : `(${l.reviews} avaliações)` }));
    } else ratingLine.append(el("span", { class: "muted", text: "Sem avaliações" }));

    const links = el("p", { class: "ld-links" });
    const m = mapsUrl(l);
    if (m) links.append(el("a", { href: m, target: "_blank", rel: "noopener noreferrer", text: "Ver no Maps" }));
    const p = pre[l.cid];
    if (p) links.append(el("a", { href: `/pre?id=${Number(p.id)}`, text: `Pré análise: ${p.score === null ? "–" : p.score}` }));
    const pu = preUrl(l);
    if (pu) links.append(el("a", { href: pu, target: "_blank", rel: "noopener noreferrer", title: "Abre o painel do negócio na busca do Google; clique em “Pré Análise SealsPro” lá", text: p ? "Refazer pré análise" : "Fazer pré análise" }));

    const logo = safeHref(l.logo);
    const head = el("div", { class: "ld-card-head" },
      logo ? el("img", { src: logo, alt: "", class: "ld-logo", loading: "lazy", referrerpolicy: "no-referrer" }) : el("span", { class: "ld-logo ld-logo-empty", "aria-hidden": "true", text: (l.name[0] || "?").toUpperCase() }),
      el("div", { class: "ld-title" }, el("h3", { text: l.name }),
        el("p", { class: "muted small", text: (l.categories || []).join(" · ") || "Sem categoria" })),
      favButton(l));
    const badges = el("p", { class: "ld-badges" },
      el("span", { class: "badge " + (l.verified ? "st-good" : "st-bad"), text: l.verified ? "Verificado" : "Não verificado" }),
      l.hits > 1 ? el("span", { class: "badge st-unavailable", title: "Quantos pontos da busca mostraram este negócio", text: `apareceu ${l.hits}×` }) : null);
    return el("article", { class: "card ld-card" }, head, ratingLine, badges, facts, qualityBlock(l), links, notesBox(l));
  }

  // ---------------- tabela ----------------
  function table(list) {
    const t = el("table", { class: "ld-table" });
    const cols = ["", "Nome", "Categoria", "Telefone", "Site", "Nota", "Avaliações", "Verificado", "Qualidade"];
    t.append(el("thead", {}, el("tr", {}, ...cols.map((c) => el("th", { text: c })))));
    const tb = el("tbody");
    for (const l of list) {
      const m = mapsUrl(l), site = safeHref(l.website);
      tb.append(el("tr", {},
        el("td", {}, favButton(l)),
        el("th", { scope: "row" }, m ? el("a", { href: m, target: "_blank", rel: "noopener noreferrer", text: l.name }) : l.name),
        el("td", { text: (l.categories || [])[0] || "" }),
        el("td", { class: "ld-nowrap", text: l.phone || "–" }),
        el("td", {}, site ? el("a", { href: site, target: "_blank", rel: "noopener noreferrer", text: siteKind(l) === "social" ? "rede social" : "site" }) : "–"),
        el("td", { class: "num", text: fmt(l.rating) }),
        el("td", { class: "num", text: l.reviews === null || l.reviews === undefined ? "–" : String(l.reviews) }),
        el("td", { text: l.verified ? "Sim" : "Não" }),
        el("td", { class: "num" }, el("span", { class: `badge st-${band(l.quality.score)}`, text: l.quality.score === null ? "–" : String(l.quality.score) }))));
    }
    t.append(tb);
    return t;
  }

  // ---------------- mapa ----------------
  function drawMap(list) {
    if (!window.L) { $("ld-map").textContent = "O mapa não carregou (sem internet?)."; return; }
    if (!map) {
      map = L.map("ld-map");
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
      layer = L.layerGroup().addTo(map);
    }
    layer.clearLayers();
    const colors = { good: "#1d6b3b", fair: "#c98a12", bad: "#b3261e", unavailable: "#55616a" };
    const pts = [];
    for (const l of list) {
      if (typeof l.lat !== "number" || typeof l.lng !== "number" || l.sab) continue;
      const pop = el("div", {}, el("strong", { text: l.name }), el("br"),
        el("span", { text: `Qualidade ${l.quality.score === null ? "–" : l.quality.score} · ${l.phone || "sem telefone"}` }));
      const m = mapsUrl(l);
      if (m) pop.append(el("br"), el("a", { href: m, target: "_blank", rel: "noopener noreferrer", text: "Ver no Maps" }));
      L.circleMarker([l.lat, l.lng], { radius: 7, color: "#fff", weight: 1.5, fillColor: colors[band(l.quality.score)], fillOpacity: .9 })
        .bindPopup(pop).addTo(layer);
      pts.push([l.lat, l.lng]);
    }
    const r = data.region;
    if (r) {
      L.rectangle([[r.south, r.west], [r.north, r.east]], { color: "#0e5a60", weight: 1, fill: false, dashArray: "4 4" }).addTo(layer);
      if (!pts.length) pts.push([r.south, r.west], [r.north, r.east]);
    }
    setTimeout(() => { map.invalidateSize(); if (pts.length) map.fitBounds(pts, { padding: [20, 20], maxZoom: 15 }); }, 0);
  }

  // ---------------- palavras ----------------
  function words() {
    const count = new Map();
    for (const l of leads) {
      for (const w of new Set(norm(l.name).split(/[^a-z0-9]+/))) {
        if (w.length > 2 && !STOP.has(w) && !/^\d+$/.test(w)) count.set(w, (count.get(w) || 0) + 1);
      }
    }
    const top = [...count.entries()].filter(([, n]) => n > 1).sort((a, b) => b[1] - a[1]).slice(0, 18);
    const box = $("ld-words");
    if (!top.length) return;
    box.append(el("p", { class: "muted small", text: "Palavras mais comuns nos nomes:" }));
    for (const [w, n] of top) {
      const b = el("button", { type: "button", class: "ld-word", title: `${n} negócios`, text: w });
      b.addEventListener("click", () => { $("ld-q").value = w; state.q = w; state.limit = PAGE; render(); });
      box.append(b);
    }
  }

  // ---------------- tela ----------------
  function render() {
    const list = current();
    $("ld-shown").textContent = `(${list.length} de ${leads.length})`;
    for (const a of document.querySelectorAll(".ld-views a")) {
      if (a.dataset.view === state.view) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    }
    $("ld-cards").hidden = state.view !== "cards";
    $("ld-table").hidden = state.view !== "table";
    $("ld-map").hidden = state.view !== "map";
    $("ld-more-wrap").hidden = true;
    if (state.view === "cards") {
      const cards = $("ld-cards");
      cards.replaceChildren(...list.slice(0, state.limit).map(card));
      if (!list.length) cards.append(el("p", { class: "card muted", text: "Nenhum lead com estes filtros." }));
      $("ld-more-wrap").hidden = list.length <= state.limit;
    } else if (state.view === "table") {
      $("ld-table").replaceChildren(table(list));
    } else {
      drawMap(list);
    }
    $("ld-dir").textContent = state.asc ? "↑ menor primeiro" : "↓ maior primeiro";
  }

  async function post(url, body) {
    try {
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      return r.ok;
    } catch (e) { return false; }
  }

  async function downloadCsv(onlyFiltered) {
    const body = { search: data.search, keys: onlyFiltered ? current().map((l) => l.key) : null };
    try {
      const r = await fetch("/leads/planilha.csv", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) throw new Error();
      const blob = await r.blob();
      const name = (/filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "") || [, "leads.csv"])[1];
      const a = el("a", { href: URL.createObjectURL(blob), download: name });
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch (e) { alert("Não foi possível gerar a planilha."); }
  }

  // eventos
  const rerender = () => { state.limit = PAGE; render(); };
  document.querySelector(".ld-filters").addEventListener("change", rerender);
  let timer = null;
  $("ld-q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { state.q = $("ld-q").value.trim(); rerender(); }, 200); });
  for (const id of ["ld-rmin", "ld-rmax", "ld-cmin", "ld-cmax", "ld-qmin", "ld-qmax"]) $(id).addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(rerender, 300); });
  $("ld-clear").addEventListener("click", () => {
    for (const i of document.querySelectorAll(".ld-filters input")) {
      if (i.type === "radio") i.checked = i.value === ""; else if (i.type === "checkbox") i.checked = false; else i.value = "";
    }
    state.q = ""; rerender();
  });
  $("ld-sort").addEventListener("change", () => {
    state.sort = $("ld-sort").value;
    state.asc = state.sort === "quality" || state.sort === "name" || state.sort === "order";
    rerender();
  });
  $("ld-dir").addEventListener("click", () => { state.asc = !state.asc; rerender(); });
  $("ld-more").addEventListener("click", () => { state.limit += PAGE; render(); });
  for (const a of document.querySelectorAll(".ld-views a")) {
    a.addEventListener("click", (e) => { e.preventDefault(); state.view = a.dataset.view; history.replaceState(null, "", a.getAttribute("href")); render(); });
  }
  for (const a of document.querySelectorAll("[data-csv]")) {
    a.addEventListener("click", (e) => { e.preventDefault(); a.closest("details").open = false; downloadCsv(a.dataset.csv === "filtered"); });
  }
  const fromHash = { "#tabela": "table", "#mapa": "map", "#cartoes": "cards" }[location.hash];
  if (fromHash) state.view = fromHash;
  words();
  render();
})();
