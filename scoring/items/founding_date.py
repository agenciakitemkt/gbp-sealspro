from scoring.base import Item, present


def evaluate(profile, now):
    date = profile["location"].get("openingDate")
    return present(bool(date), "Data de abertura cadastrada: {current}.",
                   "O perfil não informa a data de abertura.", {"current": date})


ITEM = Item("founding_date", 26, "Data de fundação", (), evaluate)
