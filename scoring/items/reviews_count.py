from scoring.base import Item, count_item


def evaluate(profile, now):
    return count_item("reviews_count", len(profile["reviews"]),
                      "O perfil tem {current} avaliações (mínimo recomendado: {recommended}).",
                      "O perfil tem só {current} avaliações; o mínimo recomendado é {recommended}.")


ITEM = Item("reviews_count", 17, "Avaliações: quantidade", ("reviews",), evaluate)
