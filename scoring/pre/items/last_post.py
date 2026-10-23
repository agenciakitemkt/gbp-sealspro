from scoring.base import Item, Outcome
from scoring.pre.base import by_score, cfg, steps


def evaluate(profile, now):
    days = profile["posts"].get("lastPostDays")
    limit = cfg("last_post")["steps"][0][0]
    if not profile["posts"].get("count") or days is None:
        return Outcome(cfg("last_post")["no_posts_score"], "O perfil não tem postagens.", {"recommended": limit})
    score = steps("last_post", days)
    return Outcome(score, by_score(score, "A última postagem foi há {current} dias (recomendado: até {recommended}).",
                                   "A última postagem foi há {current} dias; o recomendado é até {recommended}.",
                                   "A última postagem foi há {current} dias, bem acima do recomendado de até {recommended}."),
                   {"current": days, "recommended": limit})


ITEM = Item("last_post", "posts", "Data da última postagem", (), evaluate)
