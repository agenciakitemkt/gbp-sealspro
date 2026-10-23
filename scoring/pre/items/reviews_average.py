from scoring.base import Item, Outcome
from scoring.pre.base import by_score, cfg, floor_score


def evaluate(profile, now):
    c = cfg("reviews_average")
    avg = profile["reviews"].get("average")
    if not profile["reviews"].get("count") or avg is None:
        return Outcome(c["no_reviews_score"], "O perfil ainda não tem avaliações.", {})
    score = floor_score(avg, c["floors"], c["below"])
    return Outcome(score, by_score(score, "Média de {current} estrelas.",
                                   "Média de {current} estrelas, abaixo das {recommended} recomendadas.",
                                   "Média de {current} estrelas, bem abaixo das {recommended} recomendadas."),
                   {"current": avg, "recommended": c["floors"][0][0]})


ITEM = Item("reviews_average", "reviews_average", "Avaliações: média", (), evaluate)
