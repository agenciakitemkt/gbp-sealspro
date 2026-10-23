from scoring.base import Item, present


def evaluate(profile, now):
    # Decisão da Fase 0: o logotipo é a mídia da categoria PROFILE (a data 1970 que a API devolve não importa).
    has = any(m["category"] == "PROFILE" for m in profile["media"])
    return present(has, "O perfil tem logotipo.", "O perfil ainda não tem logotipo.")


ITEM = Item("logo", 6, "Mídia: logotipo", ("media",), evaluate)
