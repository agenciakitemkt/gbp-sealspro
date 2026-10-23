from scoring.base import Item, Outcome
from scoring.pre.base import cfg


def evaluate(profile, now):
    links = profile["location"].get("socialLinks") or []
    if links:
        return Outcome(100, "{current} redes sociais vinculadas ao perfil: {names}.",
                       {"current": len(links), "names": ", ".join(link["name"] for link in links)})
    return Outcome(cfg("social_links")["none_score"], "Nenhuma rede social vinculada ao perfil.", {"current": 0})


ITEM = Item("social_links", "social_links", "Redes sociais no perfil", (), evaluate)
