from scoring.base import Item, Outcome
from scoring.pre.base import by_score, steps


def evaluate(profile, now):
    size = len((profile["location"].get("description") or "").strip())
    score = steps("description", size)
    if not size:
        return Outcome(score, "O perfil não tem descrição.", {"current": 0})
    return Outcome(score, by_score(score, "A descrição tem {current} caracteres e está completa.",
                                   "A descrição tem {current} caracteres e pode ser mais detalhada.",
                                   "A descrição tem só {current} caracteres."), {"current": size})


ITEM = Item("description", "description", "Descrição da empresa", (), evaluate)
