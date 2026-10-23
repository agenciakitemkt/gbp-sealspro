from scoring.base import Item, Outcome
from scoring.pre.base import cfg, recent_window, sample


def evaluate(profile, now):
    size, recent, average = recent_window(profile)
    drop = round(average - recent, 2)
    ok = drop <= cfg("reviews_trend")["max_drop"]
    vars_ = {"recent": recent, "recentSize": size, "average": average, "size": sample(profile)["size"]}
    if not ok:
        return Outcome(0, "A média das {recentSize} avaliações mais recentes ({recent}) caiu em relação à média "
                          "das {size} analisadas ({average}).", vars_)
    trend = "subiu" if drop < 0 else "está estável"
    return Outcome(100, "A média das {recentSize} avaliações mais recentes ({recent}) " + trend +
                   " em relação à média das {size} analisadas ({average}).", vars_)


ITEM = Item("reviews_trend", "review_growth_trend", "Avaliações: tendência", ("review_sample",), evaluate)
