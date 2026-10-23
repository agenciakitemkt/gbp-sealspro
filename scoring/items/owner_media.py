from scoring.base import Item, count_item


def evaluate(profile, now):
    return count_item("owner_media", len(profile["media"]),
                      "O proprietário publicou {current} mídias (recomendado: {recommended}).",
                      "O proprietário publicou só {current} de {recommended} mídias recomendadas.")


ITEM = Item("owner_media", 14, "Mídia total pelo proprietário", ("media",), evaluate)
