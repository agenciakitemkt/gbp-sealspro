from scoring.base import Item, Outcome
from scoring.pre.base import cfg


def evaluate(profile, now):
    c = cfg("business_name")
    size = len(profile["location"]["name"].strip())
    ok = size <= c["max"]
    return Outcome(100 if ok else c["over_score"],
                   "O nome tem {current} caracteres, dentro do máximo recomendado de {recommended}." if ok else
                   "O nome tem {current} caracteres, acima do máximo recomendado de {recommended}.",
                   {"current": size, "recommended": c["max"]})


ITEM = Item("business_name", "location_name", "Nome do negócio", (), evaluate)
