from scoring.base import Item, present


def evaluate(profile, now):
    # Decisão da Fase 0: vale o período cujo início ou fim cai no ano corrente.
    periods = [p for p in profile["location"].get("specialHours") or []
               if any((p.get(k) or "")[:4] == str(now.year) for k in ("start", "end"))]
    return present(bool(periods), "Há {current} período(s) de horário especial definidos para {year}.",
                   "Nenhum horário especial definido para {year}.", {"current": len(periods), "year": now.year})


ITEM = Item("special_hours", 3, "Horário especial", (), evaluate)
