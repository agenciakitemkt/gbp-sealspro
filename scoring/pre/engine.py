"""Motor da Pre Analise: perfil normalizado da Pre entra, itens e nota geral saem. Funcao pura, sem rede nem disco.

Status por nota, nota geral e contadores sao os da Completa (scoring/base.py). Itens sem dado ficam fora da nota,
em grupos (CLAUDE.md, secao 12.3):
- review_sample: sem amostra de avaliacoes -> sem resposta, sem comentario e tendencia;
- media: sem dados de midia -> ultima foto, videos e 360;
- competitors: sem concorrentes -> top 10 e media do segmento. Aqui nos afastamos do original, que da 100 nos dois.
Alem dos grupos, o perfil pode listar em `notCollected` itens (ou grupos) cuja fonte nao foi coletada ou veio em
formato inesperado: ficam "nao avaliado". Os avisos da coleta (`warnings`) saem junto com a analise, para a tela.
"""

from datetime import datetime

from scoring.base import counters, status_for
from scoring.pre.items import ITEMS

UNAVAILABLE = {
    "review_sample": "Não foi possível coletar as avaliações recentes.",
    "media": "Não foi possível coletar as fotos e vídeos do perfil.",
    "competitors": "Não foi possível encontrar concorrentes para comparar.",
    "not_collected": "Não foi possível coletar este dado.",
}
ORDER = {item.id: n for n, item in enumerate(ITEMS)}


def missing_groups(profile):
    out = set()
    s = profile["reviews"].get("sample")
    if not s or not s.get("size"):
        out.add("review_sample")
    if profile.get("media") is None:
        out.add("media")
    comp = profile.get("competitors")
    if not comp or not comp.get("count"):
        out.add("competitors")
    return out


def _location(profile):
    loc, reviews = profile["location"], profile["reviews"]
    return {"id": loc.get("id", ""), "name": loc.get("name", ""), "category": loc.get("category", ""),
            "city": loc.get("city", ""), "address": loc.get("address", ""), "phone": loc.get("phone", ""),
            "website": loc.get("website", ""), "description": loc.get("description", ""),
            "rating": reviews.get("average"), "reviewCount": reviews.get("count") or 0,
            "starDistribution": reviews.get("starDistribution") or [0, 0, 0, 0, 0], "hours": loc.get("hours") or {},
            "mapsUrl": loc.get("mapsUrl", ""), "logoUrl": loc.get("logoUrl", ""), "coverUrl": loc.get("coverUrl", ""),
            "verified": bool(loc.get("verified"))}


def analyze(profile, now=None):
    """`now` padrao = data da coleta. Os dias (ultima postagem, foto, avaliacao) ja vem contados na coleta."""
    now = now or datetime.fromisoformat(profile["collectedAt"])
    missing = missing_groups(profile)
    skipped = set(profile.get("notCollected") or ())
    items = []
    for item in ITEMS:
        gone = sorted(set(item.requires) & missing)
        if gone:
            score, status, template, vars_ = None, "unavailable", UNAVAILABLE[gone[0]], {"sections": ", ".join(gone)}
        elif item.id in skipped or set(item.requires) & skipped:
            score, status, template, vars_ = None, "unavailable", UNAVAILABLE["not_collected"], {"sections": item.id}
        else:
            outcome = item.evaluate(profile, now)
            score, status, template, vars_ = outcome.score, status_for(outcome.score), outcome.template, outcome.vars
        items.append({"id": item.id, "originalId": item.legacy_id, "title": item.title, "score": score,
                      "status": status, "message": {"template": template, "vars": vars_}})
    # piores primeiro; sem nota ao final
    items.sort(key=lambda i: (i["score"] is None, i["score"] or 0, ORDER[i["id"]]))
    return {"location": _location(profile), "overall": counters(items), "items": items,
            "warnings": list(profile.get("warnings") or ()), "analyzedAt": now.isoformat()}
