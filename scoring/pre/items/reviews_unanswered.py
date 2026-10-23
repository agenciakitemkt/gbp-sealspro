from scoring.base import Item, Outcome
from scoring.pre.base import by_score, cfg, percent, sample


def evaluate(profile, now):
    c, s = cfg("reviews_unanswered"), sample(profile)
    pct = percent(s["unanswered"], s["size"])
    score = 100 if pct < c["good_below"] else 50 if pct <= c["fair_up_to"] else 0
    return Outcome(score, by_score(score, "{current} de {size} avaliações recentes estão sem resposta ({percent}%).",
                                   "{current} de {size} avaliações recentes estão sem resposta ({percent}%); o ideal é ficar abaixo de {recommended}%.",
                                   "{current} de {size} avaliações recentes estão sem resposta ({percent}%)."),
                   {"current": s["unanswered"], "size": s["size"], "percent": pct, "recommended": c["good_below"]})


ITEM = Item("reviews_unanswered", "reviews_without_response", "Avaliações sem resposta", ("review_sample",), evaluate)
