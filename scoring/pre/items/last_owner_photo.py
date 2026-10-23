from scoring.base import Item, Outcome
from scoring.pre.base import by_score, cfg, steps


def evaluate(profile, now):
    days = profile["media"].get("lastOwnerPhotoDays")
    limit = cfg("last_owner_photo")["steps"][0][0]
    if days is None:
        return Outcome(cfg("last_owner_photo")["no_photo_score"], "O proprietário não publicou fotos.",
                       {"recommended": limit})
    score = steps("last_owner_photo", days)
    return Outcome(score, by_score(score, "A última foto do proprietário é de {current} dias atrás.",
                                   "A última foto do proprietário é de {current} dias atrás; o recomendado é até {recommended}.",
                                   "A última foto do proprietário é de {current} dias atrás, bem acima do recomendado de até {recommended}."),
                   {"current": days, "recommended": limit})


ITEM = Item("last_owner_photo", "media_freshness", "Data da última foto do proprietário", ("media",), evaluate)
