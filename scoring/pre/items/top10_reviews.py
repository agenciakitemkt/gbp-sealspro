from scoring.base import Item
from scoring.pre.base import binary


def evaluate(profile, now):
    comp = profile["competitors"]
    return binary(bool(comp["inTop10ByReviews"]),
                  "O negócio está entre os 10 mais avaliados do segmento na região ({current} avaliações).",
                  "O negócio não está entre os 10 mais avaliados do segmento na região ({current} avaliações).",
                  {"current": profile["reviews"].get("count") or 0, "competitors": comp["count"]})


ITEM = Item("top10_reviews", "reviews_ranking_top_10", "Top 10 mais avaliados do segmento", ("competitors",), evaluate)
