from scoring.base import Item
from scoring.pre.base import binary


def evaluate(profile, now):
    return binary(bool(profile["location"].get("hours")), "O horário de funcionamento está definido.",
                  "O perfil não informa o horário de funcionamento.")


ITEM = Item("hours", "hours", "Horário de funcionamento", (), evaluate)
