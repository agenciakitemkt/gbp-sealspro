from scoring.base import Item, Outcome
from scoring.pre.base import cfg


def evaluate(profile, now):
    n = profile["media"].get("photos360") or 0
    ok = n >= cfg("photos_360")["min_count"]
    return Outcome(100 if ok else 0, "O perfil tem {current} fotos 360°." if ok else
                   "O perfil não tem fotos 360° publicadas pelo proprietário.", {"current": n})


ITEM = Item("photos_360", "360_images", "Mídia: fotos 360°", ("media",), evaluate)
