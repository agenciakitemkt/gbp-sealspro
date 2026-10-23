from scoring.base import Item, count_item


def evaluate(profile, now):
    size = len(profile["location"].get("description", "").strip())
    return count_item("description", size,
                      "A descrição tem {current} caracteres (mínimo recomendado: {recommended}).",
                      "A descrição tem só {current} caracteres; o mínimo recomendado é {recommended}.")


ITEM = Item("description", 4, "Descrição da empresa", (), evaluate)
