from scoring import config
from scoring.base import Item, Outcome
from scoring.curves import interpolate, to_score


def evaluate(profile, now):
    c = config.CONFIG["reviews_no_comment"]
    reviews = profile["reviews"]
    if not reviews:
        return Outcome(c["no_reviews_score"], "Ainda não há avaliações para medir comentários.", {"current": 0, "total": 0, "percent": 0})
    without = sum(1 for r in reviews if not r["hasComment"])
    pct = 100 * without / len(reviews)
    knots = [(c["good_max_pct"], 100), *c["measured"].items(), (c["zero_at_pct"], 0)]
    score = to_score(interpolate(pct, knots), pct <= c["good_max_pct"])
    template = ("{percent}% das avaliações vêm sem comentário, dentro do esperado." if score == 100
                else "{percent}% das avaliações ({current} de {total}) vêm sem comentário.")
    return Outcome(score, template, {"current": without, "total": len(reviews), "percent": round(pct)})


ITEM = Item("reviews_no_comment", 20, "Avaliações sem comentários", ("reviews",), evaluate)
