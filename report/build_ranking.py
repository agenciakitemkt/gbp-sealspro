"""PDF da Analise de Ranking (CLAUDE.md, secao 16, fase R5) para entregar ao cliente.

Mesma identidade e regras dos outros PDFs (Fase 6a): portugues claro, sem jargao; problemas da coleta (pontos sem
leitura) ficam so na tela. Excecao combinada com o usuario (2026-10-11): o fundo do mapa usa a internet na hora de
gerar (pedacos do OpenStreetMap, embutidos no PDF). Sem internet, o mapa sai so com a grade."""

import base64
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

import storage
from ranking import history as rk_history
from report.build import ReportError, slug

TZ = ZoneInfo("America/Sao_Paulo")
TILE = 256
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "gbp-sealspro/1.0 (SealsPro, relatorio interno)"
MAP_W, MAP_H = 660, 430   # pixels CSS do mapa no PDF (cabe na largura util do A4)
MAX_TILES = 30
TOP_COMPETITORS = 10


def fetch_tile(z, x, y):
    """Um pedaco do mapa (PNG) ou None se nao der (sem internet, recusa do servidor)."""
    try:
        r = requests.get(TILE_URL.format(z=z, x=x, y=y), headers={"User-Agent": USER_AGENT}, timeout=8)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return r.content
    except requests.RequestException:
        pass
    return None


def _world_px(lat, lng, z):
    """Coordenadas em pixels do mapa-mundi (Web Mercator) no zoom z."""
    scale = TILE * 2 ** z
    x = (lng + 180) / 360 * scale
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * scale
    return x, y


def static_map(points, fetch=fetch_tile, width=MAP_W, height=MAP_H, pad=36):
    """Mapa da grade: maior zoom em que todos os pontos cabem, pedacos do mapa como data URI e a posicao (px) de cada
    ponto. {"tiles": [{left, top, src}], "points": [{x, y}], "width", "height", "has_tiles"}."""
    lats = [p["lat"] for p in points]
    lngs = [p["lng"] for p in points]
    z = 17
    while z > 3:
        x0, y0 = _world_px(max(lats), min(lngs), z)
        x1, y1 = _world_px(min(lats), max(lngs), z)
        if x1 - x0 <= width - 2 * pad and y1 - y0 <= height - 2 * pad:
            break
        z -= 1
    cx, cy = _world_px((max(lats) + min(lats)) / 2, (max(lngs) + min(lngs)) / 2, z)
    left, top = cx - width / 2, cy - height / 2
    tiles = []
    tx0, ty0 = int(left // TILE), int(top // TILE)
    tx1, ty1 = int((left + width) // TILE), int((top + height) // TILE)
    if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) <= MAX_TILES:
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                png = fetch(z, tx % (2 ** z), ty)
                if png:
                    tiles.append({"left": round(tx * TILE - left), "top": round(ty * TILE - top),
                                  "src": "data:image/png;base64," + base64.b64encode(png).decode()})
    pts = []
    for p in points:
        x, y = _world_px(p["lat"], p["lng"], z)
        pts.append({"x": round(x - left, 1), "y": round(y - top, 1)})
    # Circulos menores em grades grandes (15x15 no mapa do PDF), sem se sobrepor
    gaps = [math.hypot(a["x"] - b["x"], a["y"] - b["y"]) for a, b in zip(pts, pts[1:])]
    gap = min([g for g in gaps if g > 0] or [60])
    pin = int(max(14, min(30, gap * 0.85)))
    return {"tiles": tiles, "points": pts, "width": width, "height": height, "has_tiles": bool(tiles),
            "pin": pin, "font": max(7, round(pin * 0.36))}


def _date(iso):
    return datetime.fromisoformat(iso).astimezone(TZ)


def _km(m):
    return f"{m / 1000:g}".replace(".", ",") + " km"


def build_ranking_report(db, ranking_id, fetch=fetch_tile):
    r = storage.get_ranking(db, ranking_id)
    if r is None:
        raise ReportError("Análise de ranking não encontrada.")
    if r["status"] != "pronta" or not r["result"]:
        raise ReportError("Só dá para gerar o PDF de uma análise pronta.")
    res = r["result"]
    location = next((l for l in storage.list_locations(db) if l["id"] == r["location_id"]), None)
    name = location["title"] if location else r["name"]
    try:
        from ranking.service import client_identity
        category = client_identity(r["location_id"])["category"]
    except Exception:  # noqa: BLE001 - so enfeite da capa
        category = ""
    when = _date(r["created_at"])
    comps = res["competitors"]
    top = comps[:TOP_COMPETITORS]
    own_row = next((c for c in comps[TOP_COMPETITORS:] if c.get("own")), None)
    unread, off = set(res.get("unread") or []), set(res.get("disabled") or [])
    cells = [{"pos": p, "unread": i in unread, "off": i in off} for i, p in enumerate(res["own"]["positions"])]

    evolution = None
    same = [x for s in rk_history.series(storage.list_rankings(db, r["location_id"]))
            if s["keyword"].strip().lower() == r["keyword"].strip().lower() and s["grid_size"] == r["grid_size"]
            and s["radius_m"] == r["radius_m"] and s["view_m"] == r["view_m"] for x in s["analyses"]]
    same = [x for x in same if (x["created_at"], x["id"]) <= (r["created_at"], r["id"])]
    if len({_date(x["created_at"]).date() for x in same}) >= 2:  # como na Completa: 2 datas diferentes
        charts = [rk_history.line_chart(same, "atrp", width=330), rk_history.line_chart(same, "solv", width=330)]
        for c in charts:
            for p in c["points"] + c["xlabels"]:
                p["date"] = _date(p["created_at"]).strftime("%d/%m/%y")
        evolution = {"charts": charts, "n": len(same)}

    return {
        "kind": "ranking", "location": {"name": name, "category": category, "city": location["city"] if location else ""},
        "keyword": r["keyword"], "grid_size": r["grid_size"], "radius": _km(r["radius_m"]), "view": _km(r["view_m"]),
        "date": when.strftime("%d/%m/%Y"), "date_label": "Ranking",
        "own": res["own"], "cells": cells, "map": static_map(r["points"], fetch=fetch),
        "competitors": top, "own_row": own_row, "own_rank": res.get("ownRank"),
        "competitors_total": res.get("competitorsTotal", len(comps)), "evolution": evolution,
        "filename": f"Ranking-{slug(name)}-{when.strftime('%Y-%m-%d')}.pdf",
    }


# ---------------------------------------------------------------------------
# Comparativo (antes e depois) de duas analises da mesma serie
# ---------------------------------------------------------------------------

def _cached(fetch):
    """As duas grades usam os mesmos pedacos do mapa: baixa cada um uma vez so."""
    cache = {}

    def get(z, x, y):
        if (z, x, y) not in cache:
            cache[(z, x, y)] = fetch(z, x, y)
        return cache[(z, x, y)]
    return get


def _fmt(metric, v, points):
    if v is None:
        return "–"
    if metric == "found":
        return f"{v} de {points}"
    if metric == "solv":
        return f"{round(v)}%"
    return f"{round(v, 1):g}".replace(".", ",")


def _fmt_delta(metric, d):
    if d is None or d == 0:
        return "="
    sign = "+" if d > 0 else "−"
    if metric == "solv":
        return f"{sign}{abs(round(d))} p.p."
    if metric == "found":
        return f"{sign}{abs(d)}"
    return sign + f"{abs(round(d, 1)):g}".replace(".", ",")


NUMBER_LABELS = {"found": "Aparece entre os 20 primeiros", "solv": "No top 3 (parte dos pontos)",
                 "arp": "Posição onde aparece (média)", "atrp": "Posição geral (média)"}


def build_ranking_comparison_report(db, a_id, b_id, fetch=fetch_tile):
    a, b = storage.get_ranking(db, a_id), storage.get_ranking(db, b_id)
    if a is None or b is None:
        raise ReportError("Uma das análises não foi encontrada.")
    if a_id == b_id:
        raise ReportError("Escolha duas análises diferentes.")
    try:
        cmp = rk_history.compare(a, b)
    except ValueError as e:
        raise ReportError(str(e)) from e
    a, b = cmp["a"], cmp["b"]
    location = next((l for l in storage.list_locations(db) if l["id"] == b["location_id"]), None)
    name = location["title"] if location else b["name"]
    fetch = _cached(fetch)
    points = b["result"]["own"]["points"]
    numbers = [{"label": NUMBER_LABELS[m["metric"]], "before": _fmt(m["metric"], m["a"], a["result"]["own"]["points"]),
                "after": _fmt(m["metric"], m["b"], points), "delta": _fmt_delta(m["metric"], m["delta"]),
                "trend": {"better": "good", "worse": "bad"}.get(m["trend"], "same")}
               for m in sorted(cmp["metrics"], key=lambda m: ("found", "solv", "arp", "atrp").index(m["metric"]))]
    c = cmp["counts"]
    found_a, found_b = a["result"]["own"]["found"], b["result"]["own"]["found"]
    if found_b > found_a:
        s1 = f"O perfil passou a aparecer em {found_b} de {points} pontos (antes, {found_a})."
    elif found_b < found_a:
        s1 = f"O perfil aparece agora em {found_b} de {points} pontos (antes, {found_a})."
    else:
        s1 = f"O perfil continua aparecendo em {found_b} de {points} pontos."
    s2 = (f"Em {c['better']} {'ponto' if c['better'] == 1 else 'pontos'} a posição melhorou"
          + (f" e em {c['worse']} piorou." if c["worse"] else ".")) if c["better"] else (
          f"A posição piorou em {c['worse']} {'ponto' if c['worse'] == 1 else 'pontos'}." if c["worse"]
          else "A posição ficou igual em todos os pontos.")

    def cells(r):
        unread, off = set(r["result"].get("unread") or []), set(r["result"].get("disabled") or [])
        return [{"pos": p, "unread": i in unread, "off": i in off} for i, p in enumerate(r["result"]["own"]["positions"])]

    same = [x for s in rk_history.series(storage.list_rankings(db, b["location_id"]))
            if rk_history.series_key(s["analyses"][-1]) == rk_history.series_key(b) for x in s["analyses"]]
    period = [x for x in same if (a["created_at"], a["id"]) <= (x["created_at"], x["id"]) <= (b["created_at"], b["id"])]
    evolution = None
    if len(period) >= 3:  # como no comparativo da Completa: 3 ou mais analises no periodo
        charts = [rk_history.line_chart(period, "atrp", width=330), rk_history.line_chart(period, "solv", width=330)]
        for ch in charts:
            for p in ch["points"] + ch["xlabels"]:
                p["date"] = _date(p["created_at"]).strftime("%d/%m/%y")
        evolution = {"charts": charts, "n": len(period)}

    day_a, day_b = _date(a["created_at"]).strftime("%d/%m/%Y"), _date(b["created_at"]).strftime("%d/%m/%Y")
    return {
        "kind": "ranking-comparativo", "location": {"name": name, "city": location["city"] if location else ""},
        "keyword": b["keyword"], "grid_size": b["grid_size"], "radius": _km(b["radius_m"]), "view": _km(b["view_m"]),
        "date": day_b, "date_label": "Comparativo de ranking", "date_before": day_a, "date_after": day_b,
        "numbers": numbers, "sentence_1": s1, "sentence_2": s2, "counts": c,
        "before": {"cells": cells(a), "map": static_map(a["points"], fetch=fetch, width=318, height=300, pad=24)},
        "after": {"cells": cells(b), "map": static_map(b["points"], fetch=fetch, width=318, height=300, pad=24)},
        "changes": cmp["points"], "competitors": cmp["competitors"], "evolution": evolution,
        "filename": f"Comparativo-Ranking-{slug(name)}-{_date(a['created_at']):%Y-%m-%d}-a-{_date(b['created_at']):%Y-%m-%d}.pdf",
    }
