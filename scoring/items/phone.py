from scoring.base import Item, present


def evaluate(profile, now):
    phone = profile["location"].get("phone", "").strip()
    return present(bool(phone), "Telefone cadastrado: {current}.",
                   "O perfil não tem telefone cadastrado.", {"current": phone})


ITEM = Item("phone", 0, "Número de telefone", (), evaluate)
