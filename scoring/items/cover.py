from scoring.base import Item, present


def evaluate(profile, now):
    has = any(m["category"] == "COVER" for m in profile["media"])
    return present(has, "O perfil tem foto de capa.", "O perfil ainda não tem foto de capa.")


ITEM = Item("cover", 7, "Mídia: foto de capa", ("media",), evaluate)
