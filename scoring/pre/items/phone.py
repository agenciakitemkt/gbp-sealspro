from scoring.base import Item
from scoring.pre.base import binary


def evaluate(profile, now):
    phone = (profile["location"].get("phone") or "").strip()
    return binary(bool(phone), "Telefone cadastrado: {current}.", "O perfil não tem telefone cadastrado.",
                  {"current": phone})


ITEM = Item("phone", "phone", "Número de telefone", (), evaluate)
