from scoring.base import Item, Outcome
from scoring.pre.base import by_score, cfg, steps


def evaluate(profile, now):
    days = profile["reviews"].get("lastReviewDays")
    limit = cfg("last_review")["steps"][0][0]
    if not profile["reviews"].get("count") or days is None:
        return Outcome(cfg("last_review")["no_reviews_score"], "O perfil ainda não tem avaliações.",
                       {"recommended": limit})
    score = steps("last_review", days)
    return Outcome(score, by_score(score, "A última avaliação chegou há {current} dias.",
                                   "A última avaliação chegou há {current} dias; o ideal é receber ao menos uma a cada {recommended}.",
                                   "A última avaliação chegou há {current} dias, bem mais que os {recommended} recomendados."),
                   {"current": days, "recommended": limit})


ITEM = Item("last_review", "last_review_date", "Data da última avaliação", (), evaluate)
