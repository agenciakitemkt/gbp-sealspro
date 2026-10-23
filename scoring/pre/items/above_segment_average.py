from scoring.base import Item
from scoring.pre.base import binary


def evaluate(profile, now):
    comp = profile["competitors"]
    n = profile["reviews"].get("count") or 0
    return binary(n >= comp["averageReviews"],
                  "{current} avaliações, acima da média do segmento na região ({average}).",
                  "{current} avaliações, abaixo da média do segmento na região ({average}).",
                  {"current": n, "average": comp["averageReviews"], "competitors": comp["count"]})


ITEM = Item("above_segment_average", "reviews_ranking_average", "Acima da média de avaliações do segmento",
            ("competitors",), evaluate)
