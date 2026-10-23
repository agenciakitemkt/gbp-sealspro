from scoring.base import Item, Outcome
from scoring.pre.base import by_score, cfg, floor_score, percent, sample


def evaluate(profile, now):
    c, s = cfg("reviews_with_text"), sample(profile)
    pct = percent(s["withText"], s["size"])
    score = floor_score(pct, c["floors"], c["below"])
    return Outcome(score, by_score(score, "{current} de {size} avaliações recentes têm comentário ({percent}%).",
                                   "{current} de {size} avaliações recentes têm comentário ({percent}%); o ideal é a partir de {recommended}%.",
                                   "Só {current} de {size} avaliações recentes têm comentário ({percent}%)."),
                   {"current": s["withText"], "size": s["size"], "percent": pct, "recommended": c["floors"][0][0]})


ITEM = Item("reviews_with_text", "reviews_without_text", "Avaliações sem comentário", ("review_sample",), evaluate)
