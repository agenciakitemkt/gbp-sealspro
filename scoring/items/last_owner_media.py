from scoring import config
from scoring.base import Item, Outcome, days_since, parse_dt
from scoring.curves import step_score


def evaluate(profile, now):
    c = config.CONFIG["last_owner_media"]
    # A API devolve 1970-01-01 em algumas mídias (ex.: perfil): não é data real.
    dates = [m["createdAt"] for m in profile["media"]
             if m.get("createdAt") and parse_dt(m["createdAt"]).year >= c["ignore_before_year"]]
    limit = c["steps"][0][0]
    if not dates:
        return Outcome(c["no_data_score"], "Nenhuma mídia do proprietário com data conhecida.", {"current": None, "recommended": limit})
    days = days_since(max(dates), now)
    score = step_score(days, c["steps"], c["beyond"])
    template = ("A última mídia do proprietário foi publicada há {current} dia(s) (limite recomendado: {recommended})." if score == 100
                else "A última mídia do proprietário tem {current} dias; o ideal é renovar a cada {recommended} dias.")
    return Outcome(score, template, {"current": days, "recommended": limit})


ITEM = Item("last_owner_media", 30, "Data da última mídia do proprietário", ("media",), evaluate)
