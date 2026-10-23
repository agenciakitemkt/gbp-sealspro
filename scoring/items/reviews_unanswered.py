from scoring import config
from scoring.base import Item, Outcome


def evaluate(profile, now):
    c = config.CONFIG["reviews_unanswered"]
    reviews = profile["reviews"]
    unanswered = sum(1 for r in reviews if not r["replied"])
    # Pela quantidade de avaliações sem resposta (hipótese); a partir de `zero_from` a nota é 0.
    score = c["no_reviews_score"] if not reviews else c["by_count"].get(unanswered, 0)
    template = ("Todas as {total} avaliações foram respondidas." if unanswered == 0
                else "{current} de {total} avaliações ainda estão sem resposta.")
    return Outcome(score, template, {"current": unanswered, "total": len(reviews)})


ITEM = Item("reviews_unanswered", 19, "Avaliações sem resposta", ("reviews",), evaluate)
