"""Evolucao e comparacao de analises de ranking (CLAUDE.md, secao 16, fase R4). Funcoes puras sobre as analises
guardadas (storage.get_ranking / list_rankings).

So se comparam analises da mesma "serie": mesmo local, mesma palavra-chave, mesma grade, mesmo raio e mesmo zoom. Com
outra grade ou outro raio os pontos nao sao os mesmos; com outra palavra ou outro zoom, a busca e outra."""

import math
from datetime import datetime, timezone

from ranking.config import NOT_FOUND_RANK, REMINDER_DAYS

METRICS = ("found", "arp", "atrp", "solv")
LOWER_IS_BETTER = {"arp", "atrp"}
CENTER_MOVED_M = 100  # o centro (o pin do perfil) mudou mais que isso entre as duas: aviso


def series_key(r):
    return (r["keyword"].strip().lower(), r["grid_size"], r["radius_m"], r["view_m"])


def series(rankings):
    """Series do local com as analises prontas em ordem cronologica: [{keyword, grid_size, radius_m, analyses}],
    da serie com a analise mais recente para a mais antiga."""
    groups = {}
    for r in sorted(rankings, key=lambda r: (r["created_at"], r["id"])):
        if r["status"] == "pronta" and r["result"]:
            groups.setdefault(series_key(r), []).append(r)
    out = [{"keyword": rs[-1]["keyword"], "grid_size": k[1], "radius_m": k[2], "view_m": k[3], "analyses": rs}
           for k, rs in groups.items()]
    out.sort(key=lambda s: s["analyses"][-1]["created_at"], reverse=True)
    return out


def line_chart(analyses, metric, width=360, height=170):
    """Geometria de um grafico pequeno de uma metrica (pontos igualmente espacados, como o da Completa).
    ATRP e ARP: eixo invertido (1 em cima), para "subir" ser melhor."""
    left, right, top, bottom = 34, 40, 16, 34
    plot_w, plot_h = width - left - right, height - top - bottom
    if metric in LOWER_IS_BETTER:
        lo, hi, ticks = 1, NOT_FOUND_RANK, (1, 5, 10, 15, 21)
        def y(v):
            return top + plot_h * (v - lo) / (hi - lo)
    else:
        lo, hi, ticks = 0, 100, (0, 25, 50, 75, 100)
        def y(v):
            return top + plot_h * (1 - (v - lo) / (hi - lo))
    pts = [r for r in analyses if r["result"]["own"].get(metric) is not None]
    n = len(pts)

    def x(i):
        return left + plot_w / 2 if n == 1 else left + plot_w * i / (n - 1)
    points = [{"id": r["id"], "x": round(x(i), 1), "y": round(y(r["result"]["own"][metric]), 1),
               "value": r["result"]["own"][metric], "created_at": r["created_at"]} for i, r in enumerate(pts)]
    step = max(1, math.ceil(n / 5))
    return {"width": width, "height": height, "left": left, "right": width - right, "top": top,
            "bottom": top + plot_h, "n": n, "metric": metric,
            "grid": [{"y": round(y(t), 1), "label": str(t)} for t in ticks],
            "points": points, "line": " ".join(f"{p['x']},{p['y']}" for p in points),
            "xlabels": [{"x": p["x"], "created_at": p["created_at"]} for i, p in enumerate(points) if i % step == 0]}


def _distance_m(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return 0
    k = 111320
    return math.hypot((lat2 - lat1) * k, (lng2 - lng1) * k * math.cos(math.radians((lat1 + lat2) / 2)))


def _delta(metric, a, b):
    if a is None or b is None:
        return None, "same"
    d = round(b - a, 2)
    if d == 0:
        return 0, "same"
    better = d < 0 if metric in LOWER_IS_BETTER else d > 0
    return d, "better" if better else "worse"


def _rank(p):
    return NOT_FOUND_RANK if p is None else p


def compare(a, b):
    """Compara duas analises prontas da mesma serie. A mais antiga e o "antes", qualquer que seja a ordem pedida.
    Levanta ValueError (mensagem para a tela) se nao forem comparaveis."""
    if a["status"] != "pronta" or b["status"] != "pronta" or not a["result"] or not b["result"]:
        raise ValueError("As duas análises precisam estar prontas.")
    if a["location_id"] != b["location_id"]:
        raise ValueError("As duas análises precisam ser do mesmo local.")
    if series_key(a) != series_key(b):
        raise ValueError("Só dá para comparar análises com a mesma palavra-chave, grade, raio e zoom.")
    if (b["created_at"], b["id"]) < (a["created_at"], a["id"]):
        a, b = b, a
    oa, ob = a["result"]["own"], b["result"]["own"]
    metrics = []
    for m in METRICS:
        d, trend = _delta(m, oa.get(m), ob.get(m))
        metrics.append({"metric": m, "a": oa.get(m), "b": ob.get(m), "delta": d, "trend": trend})

    unread = set(a["result"].get("unread") or []) | set(b["result"].get("unread") or [])
    off = set(a["result"].get("disabled") or []) | set(b["result"].get("disabled") or [])
    points, counts = [], {"better": 0, "worse": 0, "same": 0, "unread": 0, "off": 0}
    for i, (pa, pb) in enumerate(zip(oa["positions"], ob["positions"])):
        if i in off:
            trend = "off"
        elif i in unread:
            trend = "unread"
        elif _rank(pb) < _rank(pa):
            trend = "better"
        elif _rank(pb) > _rank(pa):
            trend = "worse"
        else:
            trend = "same"
        counts[trend] += 1
        points.append({"i": i, "a": pa, "b": pb, "trend": trend})

    before = {(c.get("placeId") or c.get("cid")): c for c in a["result"]["competitors"]}
    rows = []
    for c in b["result"]["competitors"][:10] + [c for c in b["result"]["competitors"][10:] if c.get("own")]:
        old = before.get(c.get("placeId") or c.get("cid"))
        d, trend = _delta("atrp", old["atrp"] if old else None, c["atrp"])
        rows.append({"name": c["name"], "own": c.get("own"), "a_atrp": old["atrp"] if old else None, "b_atrp": c["atrp"],
                     "a_solv": old["solv"] if old else None, "b_solv": c["solv"], "delta": d, "trend": trend,
                     "new": old is None})
    moved = _distance_m(a["center_lat"], a["center_lng"], b["center_lat"], b["center_lng"])
    return {"a": a, "b": b, "metrics": metrics, "points": points, "counts": counts, "competitors": rows,
            "center_moved_m": round(moved) if moved > CENTER_MOVED_M else None}


def due(rankings, now=None, days=REMINDER_DAYS):
    """Lembrete: series cuja ultima analise pronta tem mais de `days` dias e que nao tem outra analise pendente ou em
    coleta depois dela. rankings: de varios locais. Devolve [{"last", "days"}], das mais atrasadas para as menos."""
    now = now or datetime.now(timezone.utc)
    by_series = {}
    for r in sorted(rankings, key=lambda r: (r["created_at"], r["id"])):
        by_series.setdefault((r["location_id"],) + series_key(r), []).append(r)
    out = []
    for rs in by_series.values():
        ready = [r for r in rs if r["status"] == "pronta"]
        if not ready:
            continue
        last = ready[-1]
        if any(r["status"] in ("pendente", "coletando") and (r["created_at"], r["id"]) > (last["created_at"], last["id"])
               for r in rs):
            continue  # ja foi repetida e esta em andamento
        age = (now - datetime.fromisoformat(last["created_at"])).days
        if age > days:
            out.append({"last": last, "days": age})
    out.sort(key=lambda d: -d["days"])
    return out
