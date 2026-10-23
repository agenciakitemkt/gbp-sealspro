"""Fase 5a: evolucao ao longo do tempo (so Analise Completa).

Logica pura e leitura: geometria do grafico, diferenca entre duas analises e diferenca entre os dados do perfil.
Nada aqui grava no banco. A reavaliacao com o motor atual e calculada em memoria.
"""

import math
from datetime import datetime

import storage
from collector.normalize import normalize
from scoring import analyze, config

STARS = (5, 4, 3, 2, 1)


# ---------------------------------------------------------------------------
# Versao
# ---------------------------------------------------------------------------

def version_key(analysis):
    return (analysis["engine_version"], analysis["config_hash"])


def version_label(analysis):
    """'v1 · 3fa9c2d1' ou 'desconhecida' (analises feitas antes da Fase 5a)."""
    if analysis["engine_version"] == "desconhecida" or not analysis["config_hash"]:
        return "desconhecida"
    return f"v{analysis['engine_version']} · {analysis['config_hash'][:8]}"


# ---------------------------------------------------------------------------
# Grafico da nota geral (SVG inline renderizado no template)
# ---------------------------------------------------------------------------

def build_chart(analyses, bands=None, width=760, height=300):
    """Geometria do grafico. Pontos igualmente espacados na ordem das analises (nao proporcionais ao tempo)."""
    bands = bands or config.OVERALL_BANDS
    left, right, top, bottom = 46, 76, 30, 58
    plot_w, plot_h = width - left - right, height - top - bottom
    points = [a for a in analyses if a["score"] is not None]
    n = len(points)

    def x(i):
        return left + plot_w / 2 if n == 1 else left + plot_w * i / (n - 1)

    def y(score):
        return top + plot_h * (1 - score / 100)

    fair, good = bands["fair_from"], bands["good_from"]
    chart = {
        "width": width, "height": height, "left": left, "right": width - right, "n": n,
        "bands": [{"cls": "bad", "label": "Fraco", "y": y(fair), "h": y(0) - y(fair)},
                  {"cls": "fair", "label": "Razoável", "y": y(good), "h": y(fair) - y(good)},
                  {"cls": "good", "label": "Bom", "y": y(100), "h": y(good) - y(100)}],
        "grid": [{"y": y(v), "label": str(v)} for v in (0, 25, 50, 75, 100)],
        "points": [], "xlabels": [], "markers": [], "line": "",
    }
    step = max(1, math.ceil(n / 8))
    for i, a in enumerate(points):
        py = y(a["score"])
        chart["points"].append({
            "id": a["id"], "x": round(x(i), 1), "y": round(py, 1), "score": a["score"], "kind": a["kind"],
            "analyzed_at": a["analyzed_at"], "version": version_label(a),
            "label_y": round(py - 11 if py - 11 > top - 4 else py + 20, 1)})
        if i % step == 0:
            chart["xlabels"].append({"x": round(x(i), 1), "analyzed_at": a["analyzed_at"]})
        if i and version_key(a) != version_key(points[i - 1]):
            chart["markers"].append({"x": round((x(i - 1) + x(i)) / 2, 1),
                                     "text": f"{version_label(points[i - 1])} → {version_label(a)}"})
    chart["line"] = " ".join(f"{p['x']},{p['y']}" for p in chart["points"])
    chart["plot_top"], chart["plot_bottom"] = top, top + plot_h
    return chart


# ---------------------------------------------------------------------------
# Diferenca entre duas analises: itens
# ---------------------------------------------------------------------------

def items_diff(result_a, result_b):
    a = {i["legacyId"]: i for i in result_a["items"]}
    b = {i["legacyId"]: i for i in result_b["items"]}
    rows = []
    for item_id in sorted(set(a) | set(b)):
        ia, ib = a.get(item_id), b.get(item_id)
        sa, sb = (ia or {}).get("score"), (ib or {}).get("score")
        sta, stb = (ia or {}).get("status", "ausente"), (ib or {}).get("status", "ausente")
        rows.append({"id": item_id, "title": (ib or ia)["title"], "a": ia, "b": ib,
                     "a_score": sa, "b_score": sb, "a_status": sta, "b_status": stb,
                     "delta": sb - sa if sa is not None and sb is not None else None,
                     "changed": (sa, sta) != (sb, stb)})
    oa, ob = result_a["overall"], result_b["overall"]
    delta = lambda k: ob[k] - oa[k] if oa.get(k) is not None and ob.get(k) is not None else None  # noqa: E731
    return {"rows": rows, "changed": [r for r in rows if r["changed"]],
            "unchanged": [r for r in rows if not r["changed"]],
            "overall": {"a": oa, "b": ob, **{f"d_{k}": delta(k) for k in ("score", "good", "fair", "bad")}}}


# ---------------------------------------------------------------------------
# Diferenca entre duas analises: dados do perfil
# ---------------------------------------------------------------------------

def _day(iso):
    return iso[:10] if iso else None


def facts(profile):
    """Contagens e datas (e nome e descricao como texto). Nunca texto de avaliacoes de clientes."""
    loc = profile["location"]
    reviews, media = profile["reviews"], profile["media"]
    min_year = config.CONFIG["last_owner_media"]["ignore_before_year"]
    own_dates = [m["createdAt"] for m in media
                 if m.get("createdAt") and datetime.fromisoformat(m["createdAt"]).year >= min_year]
    posts = [p["createdAt"] for p in profile["posts"] if p.get("createdAt")]
    review_dates = [r["createdAt"] for r in reviews if r.get("createdAt")]
    videos = sum(1 for m in media if m["format"] == "VIDEO")
    return {
        "reviews": len(reviews), "rating": loc["rating"], "stars": list(loc["starDistribution"]),
        "unanswered": sum(1 for r in reviews if not r["replied"]),
        "no_comment": sum(1 for r in reviews if not r["hasComment"]),
        "last_review": _day(max(review_dates)) if review_dates else None,
        "owner_media": len(media), "photos": len(media) - videos, "videos": videos,
        "customer_media": len(profile["customerMedia"]),
        "last_owner_media": _day(max(own_dates)) if own_dates else None,
        "posts": len(posts), "last_post": _day(max(posts)) if posts else None,
        "name": loc["name"], "description": loc["description"],
    }


_ROWS = (  # (grupo, rotulo, chave, tipo)
    ("Avaliações", "Total de avaliações", "reviews", "number"),
    ("Avaliações", "Nota média", "rating", "number"),
    ("Avaliações", "Estrelas (5★ a 1★)", "stars", "list"),
    ("Avaliações", "Sem resposta", "unanswered", "number"),
    ("Avaliações", "Sem comentário", "no_comment", "number"),
    ("Avaliações", "Avaliação mais recente", "last_review", "date"),
    ("Mídias", "Mídias do proprietário", "owner_media", "number"),
    ("Mídias", "Fotos", "photos", "number"),
    ("Mídias", "Vídeos", "videos", "number"),
    ("Mídias", "Mídias de clientes", "customer_media", "number"),
    ("Mídias", "Última mídia do proprietário", "last_owner_media", "date"),
    ("Postagens", "Total de postagens", "posts", "number"),
    ("Postagens", "Última postagem", "last_post", "date"),
    ("Texto do perfil", "Nome", "name", "text"),
    ("Texto do perfil", "Descrição", "description", "text"),
)


def profile_diff(profile_a, profile_b):
    fa, fb = facts(profile_a), facts(profile_b)
    rows = []
    for group, label, key, kind in _ROWS:
        a, b = fa[key], fb[key]
        row = {"group": group, "label": label, "kind": kind, "a": a, "b": b, "changed": a != b,
               "delta": None, "delta_days": None}
        if kind == "number" and a is not None and b is not None:
            row["delta"] = round(b - a, 2)
        elif kind == "date" and a and b:
            row["delta_days"] = (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Comparacao completa (leitura apenas)
# ---------------------------------------------------------------------------

def load_profile(analysis):
    """Perfil normalizado a partir do bruto guardado da analise, ou None se o bruto nao existir mais."""
    raw = storage.load_raw_file(analysis["raw_path"])
    return None if raw is None else normalize(raw)


def build_comparison(db, a_id, b_id, reevaluate=False):
    """Compara duas analises do mesmo local. Nao grava nada: com `reevaluate`, as notas sao recalculadas com o
    motor atual em memoria, a partir dos brutos.

    LookupError se alguma analise nao existir; ValueError se forem de locais diferentes.
    """
    a, b = storage.get_analysis(db, a_id), storage.get_analysis(db, b_id)
    if a is None or b is None:
        raise LookupError("analise nao encontrada")
    if a["location_id"] != b["location_id"]:
        raise ValueError("as analises sao de locais diferentes")
    profiles = {"a": load_profile(a), "b": load_profile(b)}
    results, reevaluated = {"a": a["result"], "b": b["result"]}, {"a": False, "b": False}
    if reevaluate:
        for side in ("a", "b"):
            if profiles[side] is not None:
                results[side], reevaluated[side] = analyze(profiles[side]), True
    notices = []
    for side, label in (("a", "A"), ("b", "B")):
        if profiles[side] is None:
            notices.append(f"O bruto da análise {label} não está mais disponível: "
                           + ("não foi possível reavaliá-la e " if reevaluate else "")
                           + "os dados do perfil não podem ser comparados.")
    return {
        "a": a, "b": b, "location_id": a["location_id"],
        "versions_differ": version_key(a) != version_key(b),
        "reevaluate": reevaluate, "reevaluated": reevaluated,
        "items": items_diff(results["a"], results["b"]),
        "data": profile_diff(profiles["a"], profiles["b"]) if all(profiles.values()) else None,
        "notices": notices,
    }
