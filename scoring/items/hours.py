from scoring.base import Item, present


def evaluate(profile, now):
    days = len(profile["location"].get("hours") or {})
    return present(days > 0, "O horário normal está definido para {current} dia(s) da semana.",
                   "O perfil não tem horário de funcionamento definido.", {"current": days})


ITEM = Item("hours", 2, "Horário de funcionamento", (), evaluate)
