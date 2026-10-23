from scoring.base import Item, count_item


def evaluate(profile, now):
    videos = sum(1 for m in profile["media"] if m["format"] == "VIDEO")
    return count_item("videos", videos,
                      "{current} vídeos publicados pelo proprietário (recomendado: {recommended}).",
                      "Só {current} de {recommended} vídeos recomendados foram publicados pelo proprietário.")


ITEM = Item("videos", 5, "Mídia: vídeos", ("media",), evaluate)
