"""Motor de nota: perfil normalizado entra, itens e nota geral saem. Função pura, sem rede nem disco."""

from datetime import datetime

from scoring.base import counters, status_for
from scoring.items import ITEMS

LOCATION_KEYS = ("id", "name", "category", "city", "address", "phone", "website", "description", "rating",
                 "reviewCount", "starDistribution", "hours", "mapsUrl", "searchUrl", "logoUrl", "coverUrl")

UNAVAILABLE = "Não foi possível coletar este dado."  # `sections` vai em vars (para depuração), não no texto
# Texto que as analises guardadas ate a Fase 5a trazem no JSON; a tela o troca pelo atual ao exibir.
UNAVAILABLE_LEGACY = ("Não foi possível avaliar este item: os dados de {sections} não puderam ser coletados.",)


def _unavailable_sections(profile):
    sections = set(profile.get("collectionErrors") or {})
    if not profile.get("reviewsComplete", True):
        sections.add("reviews")  # lista incompleta daria contagens erradas
    return sections


def analyze(profile, now=None):
    """`now` padrão = data da coleta, para o resultado depender só do perfil."""
    now = now or datetime.fromisoformat(profile["collectedAt"])
    broken = _unavailable_sections(profile)
    items = []
    for item in ITEMS:
        missing = sorted(set(item.requires) & broken)
        if item.applies and not item.applies(profile):
            score, status, template, vars_ = None, "not_applicable", item.not_applicable_template, {}
        elif missing:
            score, status, template, vars_ = None, "unavailable", UNAVAILABLE, {"sections": ", ".join(missing)}
        else:
            outcome = item.evaluate(profile, now)
            score, status, template, vars_ = outcome.score, status_for(outcome.score), outcome.template, outcome.vars
        items.append({"id": item.id, "legacyId": item.legacy_id, "title": item.title, "score": score,
                      "status": status, "message": {"template": template, "vars": vars_}})
    # piores primeiro; sem nota ao final (indisponiveis, depois os que nao se aplicam)
    items.sort(key=lambda i: (i["score"] is None, i["status"] == "not_applicable", i["score"] or 0, i["legacyId"]))

    return {
        "location": {k: profile["location"][k] for k in LOCATION_KEYS},
        "overall": counters(items),
        "items": items,
        "analyzedAt": now.isoformat(),
    }
