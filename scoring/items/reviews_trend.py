from scoring import config
from scoring.base import Item, Outcome, days_since


def _avg(reviews):
    return sum(r["rating"] for r in reviews) / len(reviews)


def evaluate(profile, now):
    c = config.CONFIG["reviews_trend"]
    recent = [r for r in profile["reviews"] if days_since(r["createdAt"], now) <= c["recent_days"]]
    older = [r for r in profile["reviews"] if days_since(r["createdAt"], now) > c["recent_days"]]
    if not recent or not older:
        trend, template = c["insufficient_data"], "Ainda não há avaliações suficientes (recentes e antigas) para comparar a evolução."
        return Outcome(c["scores"][trend], template, {"trend": trend, "days": c["recent_days"]})
    delta = round(_avg(recent) - _avg(older), 2)
    trend = "up" if delta >= c["stable_delta"] else "down" if delta <= -c["stable_delta"] else "stable"
    template = {
        "up": "A média das avaliações dos últimos {days} dias ({recent}) está acima da histórica ({historical}).",
        "stable": "A média das avaliações dos últimos {days} dias ({recent}) acompanha a histórica ({historical}).",
        "down": "A média das avaliações dos últimos {days} dias ({recent}) está abaixo da histórica ({historical}).",
    }[trend]
    return Outcome(c["scores"][trend], template, {"trend": trend, "days": c["recent_days"],
                                                   "recent": round(_avg(recent), 2),
                                                   "historical": round(_avg(older), 2), "delta": delta})


ITEM = Item("reviews_trend", 28, "Avaliações: comparativo", ("reviews",), evaluate)
