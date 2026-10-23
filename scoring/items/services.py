from scoring.base import Item, present


def applies(profile):
    # Hipotese apoiada em 1 caso (um local de energia solar): o original nao avalia Servicos quando a categoria nao aceita
    # lista de servicos, o que a API sinaliza pela ausencia de metadata.canModifyServiceList. Sem `metadata`
    # (None) nao ha como saber: o item continua valendo.
    return profile["location"].get("servicesEditable") is not False


def evaluate(profile, now):
    n = len(profile["location"].get("services") or [])
    return present(n > 0, "O perfil lista {current} serviço(s).",
                   "O perfil não tem serviços cadastrados.", {"current": n})


ITEM = Item("services", 25, "Serviços", (), evaluate, applies,
            "O Google não oferece lista de serviços para a categoria deste perfil; o item fica fora da nota.")
