from scoring.base import Item, count_item


def evaluate(profile, now):
    total = len(profile["media"]) + len(profile["customerMedia"])
    return count_item("total_media", total,
                      "O perfil reúne {current} mídias no total (recomendado: {recommended}).",
                      "O perfil reúne só {current} de {recommended} mídias recomendadas no total.")


ITEM = Item("total_media", 15, "Mídia total", ("media", "mediaCustomers"), evaluate)
