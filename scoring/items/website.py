from scoring.base import Item, present


def evaluate(profile, now):
    site = profile["location"].get("website", "").strip()
    return present(bool(site), "O perfil aponta para o site {current}.",
                   "O perfil não tem endereço de site cadastrado.", {"current": site})


ITEM = Item("website", 1, "Website", (), evaluate)
