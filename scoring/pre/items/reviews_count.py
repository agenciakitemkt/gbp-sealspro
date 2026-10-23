from scoring.base import Item, Outcome
from scoring.pre.base import cfg, count


def evaluate(profile, now):
    n = profile["reviews"].get("count") or 0
    score = count("reviews_count", n)
    return Outcome(score, "{current} avaliações (mínimo recomendado: {recommended})." if score == 100 else
                   "Só {current} avaliações; o mínimo recomendado é {recommended}.",
                   {"current": n, "recommended": cfg("reviews_count")["recommended"]})


ITEM = Item("reviews_count", "reviews_quantity", "Avaliações: quantidade", (), evaluate)
