from scoring.base import Item
from scoring.pre.base import binary


def evaluate(profile, now):
    return binary(bool(profile["location"].get("logoUrl")), "O perfil tem logotipo.", "O perfil não tem logotipo.")


ITEM = Item("logo", "logo", "Mídia: logotipo", (), evaluate)
