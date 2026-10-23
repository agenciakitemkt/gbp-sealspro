from scoring.base import Item, Outcome
from scoring.pre.base import cfg, count


def evaluate(profile, now):
    videos = profile["media"].get("videos") or 0
    score = count("videos", videos)
    return Outcome(score, "{current} vídeos publicados (recomendado: {recommended})." if score == 100 else
                   "Só {current} de {recommended} vídeos recomendados foram publicados.",
                   {"current": videos, "recommended": cfg("videos")["recommended"]})


ITEM = Item("videos", "videos", "Mídia: vídeos", ("media",), evaluate)
