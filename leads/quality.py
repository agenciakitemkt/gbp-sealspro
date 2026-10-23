"""Qualidade estimada do perfil de um lead, so com o que a busca do Maps traz (nada e coletado a mais).

Usa os itens da Pre Analise (scoring/pre/items) que a busca alimenta, com os mesmos cortes, e a mesma nota geral
(scoring/base.py): telefone, site (rede social = 50), horario, logotipo, verificado, quantidade e media de avaliacoes.
Assim a nota do lead fica na mesma escala da pre analise que ele recebera se virar abordagem (a pre analise tem mais
itens; os que faltam aqui, como descricao, postagens e fotos, so ela mede). Quando a busca traz a nota mas nao a
quantidade de avaliacoes, a quantidade fica fora da conta.
"""

from scoring.base import counters, status_for
from scoring.pre.items import hours, logo, phone, reviews_average, reviews_count, verified, website

ITEMS = (("phone", "Telefone", phone), ("website", "Site", website), ("hours", "Horário", hours),
         ("logo", "Logotipo", logo), ("verified", "Verificado", verified),
         ("reviews_count", "Quantidade de avaliações", reviews_count),
         ("reviews_average", "Média das avaliações", reviews_average))


def quality(lead):
    """Lead -> {"score", "items": [{"id", "title", "score", "status"}], "good", "fair", "bad"}."""
    count = lead.get("reviews")
    unknown_count = count is None and lead.get("rating") is not None
    profile = {"location": {"phone": lead.get("phone"), "website": lead.get("website"), "hours": lead.get("hours"),
                            "logoUrl": lead.get("logo"), "verified": lead.get("verified")},
               "reviews": {"count": count if count is not None else (1 if unknown_count else 0),
                           "average": lead.get("rating")}}
    items = []
    for item_id, title, module in ITEMS:
        if item_id == "reviews_count" and unknown_count:
            items.append({"id": item_id, "title": title, "score": None, "status": "unavailable"})
            continue
        score = module.ITEM.evaluate(profile, None).score
        items.append({"id": item_id, "title": title, "score": score, "status": status_for(score)})
    c = counters(items)
    return {"score": c["score"], "good": c["good"], "fair": c["fair"], "bad": c["bad"], "items": items}
