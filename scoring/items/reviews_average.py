from scoring import config
from scoring.base import Item, Outcome
from scoring.curves import interpolate, to_score


def evaluate(profile, now):
    c = config.CONFIG["reviews_average"]
    if not profile["reviews"]:
        return Outcome(c["no_reviews_score"], "O perfil ainda não tem avaliações para calcular a média.", {"current": 0.0})
    rating = profile["location"]["rating"]
    score = to_score(interpolate(rating, c["knots"]), rating >= c["good_from"])
    template = ("A média das avaliações é {current} estrelas." if score == 100
                else "A média das avaliações é {current} estrelas, abaixo do nível desejado ({recommended}).")
    return Outcome(score, template, {"current": rating, "recommended": c["good_from"]})


ITEM = Item("reviews_average", 18, "Avaliações: média", ("reviews",), evaluate)
