from scoring import config
from scoring.base import Item, Outcome, days_since
from scoring.curves import step_score


def evaluate(profile, now):
    c = config.CONFIG["last_post"]
    dates = [p["createdAt"] for p in profile["posts"] if p.get("createdAt")]
    if not dates:
        return Outcome(c["no_data_score"], "Nenhuma postagem encontrada no perfil.", {"current": None, "recommended": c["steps"][0][0]})
    days = days_since(max(dates), now)
    score = step_score(days, c["steps"], c["beyond"])
    template = ("A última postagem foi há {current} dia(s) (limite recomendado: {recommended})." if score == 100
                else "A última postagem foi há {current} dias; o ideal é publicar a cada {recommended} dias.")
    return Outcome(score, template, {"current": days, "recommended": c["steps"][0][0]})


ITEM = Item("last_post", 29, "Data da última postagem", ("localPosts",), evaluate)
