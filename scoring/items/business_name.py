from scoring import config
from scoring.base import Item, present


def evaluate(profile, now):
    limit = config.CONFIG["business_name"]["max_chars"]
    size = len(profile["location"]["name"].strip())
    return present(0 < size <= limit, "O nome do negócio tem {current} caracteres (máximo recomendado: {recommended}).",
                   "O nome do negócio tem {current} caracteres, fora do limite recomendado de {recommended}.",
                   {"current": size, "recommended": limit})


ITEM = Item("business_name", 27, "Nome do negócio", (), evaluate)
