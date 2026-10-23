from scoring.base import Item, count_item


def evaluate(profile, now):
    return count_item("customer_media", len(profile["customerMedia"]),
                      "Clientes publicaram {current} mídias no perfil (recomendado: {recommended}).",
                      "Clientes publicaram só {current} de {recommended} mídias recomendadas no perfil.")


ITEM = Item("customer_media", 16, "Mídias publicadas por clientes", ("mediaCustomers",), evaluate)
