from scoring.base import Item
from scoring.pre.base import binary


def evaluate(profile, now):
    return binary(bool(profile["location"].get("verified")), "O perfil é verificado pelo Google.",
                  "O perfil não é verificado pelo Google.")


ITEM = Item("verified", "is_verified", "Perfil verificado", (), evaluate)
