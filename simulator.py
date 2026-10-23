"""Simulador de avaliacoes: quantas avaliacoes faltam para a nota do Google subir de faixa, em quanto tempo e quantas
avaliacoes ruins a fariam cair. Funcao pura sobre a distribuicao de estrelas (5 -> 1) guardada na analise.

O Google mostra a media com uma casa decimal, arredondando para cima a partir de 0,05 (4,25 aparece como 4,3). Todas
as contas usam inteiros em decimos para nao errar por arredondamento de ponto flutuante:
- a nota mostrada e >= t (em decimos) quando 20 x soma >= (2t - 1) x total;
- a nota mostrada e <= t quando 20 x soma < (2t + 1) x total.

Faixas proprias da SealsPro (os limites seguem os do simulador do GBP Check, que usa cinco faixas parecidas).
"""

import math
from datetime import date, timedelta

# (chave, nome, de, ate), em decimos de estrela, da pior para a melhor
ZONES = (
    ("muito_baixa", "Muito baixa", 10, 29),
    ("baixa", "Baixa", 30, 38),
    ("regular", "Regular", 39, 42),
    ("boa", "Boa", 43, 46),
    ("excelente", "Excelente", 47, 50),
)
PERIODS = {"dia": 1, "semana": 7, "mes": 30}
PERIOD_NAMES = {"dia": "dia", "semana": "semana", "mes": "mês"}
PACES = {  # ritmos prontos de avaliacoes 5 estrelas por periodo
    "dia": (("Devagar", 1), ("Constante", 3), ("Intenso", 5)),
    "semana": (("Devagar", 2), ("Constante", 5), ("Intenso", 10)),
    "mes": (("Devagar", 5), ("Constante", 15), ("Intenso", 30)),
}
SCENARIOS = ((1, "Avaliações de 1 estrela"), (2, "Avaliações de 2 estrelas"), (3, "Avaliações de 3 estrelas"))
MAX_REVIEWS = 100000


class SimulatorError(ValueError):
    """Dados insuficientes para simular. A mensagem pode ser mostrada na tela."""


def totals(star_distribution, rating=None, count=None):
    """(soma das estrelas, total de avaliacoes). Usa a distribuicao (posicao 0 = 5 estrelas); sem ela, estima pela
    media e pela quantidade."""
    if star_distribution and sum(star_distribution) > 0:
        dist = [int(n or 0) for n in star_distribution]
        return sum(n * (5 - i) for i, n in enumerate(dist)), sum(dist)
    if count and rating:
        return round(rating * count), int(count)
    return 0, 0


def shown(total_stars, total):
    """Nota que o Google mostra, em decimos (None sem avaliacoes)."""
    if not total:
        return None
    return (20 * total_stars + total) // (2 * total)  # floor(media x 10 + 0,5)


def zone_of(tenths):
    for key, name, low, high in ZONES:
        if tenths is not None and low <= tenths <= high:
            return {"key": key, "name": name, "low": low, "high": high}
    return {"key": ZONES[0][0], "name": ZONES[0][1], "low": ZONES[0][2], "high": ZONES[0][3]}


def needed_for(total_stars, total, target):
    """Avaliacoes de 5 estrelas para a nota mostrada chegar a `target` (decimos). 0 se ja chegou."""
    gap = (2 * target - 1) * total - 20 * total_stars
    if gap <= 0:
        return 0
    return math.ceil(gap / (101 - 2 * target))


def to_drop(total_stars, total, stars, ceiling):
    """Avaliacoes de `stars` estrelas para a nota mostrada cair a `ceiling` (decimos) ou menos; None se nao cai."""
    if not total:
        return None
    limit = 2 * ceiling + 1
    room = 20 * total_stars - limit * total
    if room < 0:
        return 0
    if limit - 20 * stars <= 0:
        return None  # com essas estrelas a media nunca desce ate la
    return room // (limit - 20 * stars) + 1


def _tenths(value):
    return f"{value // 10},{value % 10}"


def duration(days):
    if days <= 0:
        return "menos de 1 dia"
    months, rest = divmod(days, 30)
    weeks, d = divmod(rest, 7)
    parts = []
    if months:
        parts.append(f"{months} {'mês' if months == 1 else 'meses'}")
    if weeks:
        parts.append(f"{weeks} {'semana' if weeks == 1 else 'semanas'}")
    if d and not months:
        parts.append(f"{d} {'dia' if d == 1 else 'dias'}")
    return " e ".join(parts)


def simulate(star_distribution, rating=None, count=None, target=None, pace=5, period="semana", today=None):
    total_stars, total = totals(star_distribution, rating, count)
    if not total:
        raise SimulatorError("O perfil ainda não tem avaliações: não há nota para simular.")
    period = period if period in PERIODS else "semana"
    pace = max(1, min(int(pace or 1), 1000))
    today = today or date.today()
    current = shown(total_stars, total)
    zone = zone_of(current)
    zone_index = [z[0] for z in ZONES].index(zone["key"])

    targets = list(range(current + 1, 51))  # metas possiveis: acima da nota atual
    if target not in targets:
        above = [z for z in ZONES[zone_index + 1:]]
        target = above[0][2] if above else None
    needed = needed_for(total_stars, total, target) if target else 0

    plan = None
    if target and needed:
        periods = math.ceil(needed / pace)
        days = periods * PERIODS[period]
        plan = {"periods": periods, "days": days, "duration": duration(days),
                "date": (today + timedelta(days=days)).strftime("%d/%m/%Y")}

    paces = []
    for name, n in PACES[period]:
        days = math.ceil(needed / n) * PERIODS[period] if needed else 0
        paces.append({"name": name, "pace": n, "duration": duration(days) if needed else None, "active": n == pace})

    growth = [{"zone": name, "target": _tenths(low), "needed": needed_for(total_stars, total, low)}
              for key, name, low, high in ZONES[zone_index + 1:]]

    risk = []
    if zone_index > 0:
        below = ZONES[zone_index - 1]
        for stars, label in SCENARIOS:
            n = to_drop(total_stars, total, stars, below[3])
            if n:
                after = shown(total_stars + stars * n, total + n)
                risk.append({"stars": stars, "label": label, "count": n, "zone": zone_of(after)["name"],
                             "after": _tenths(after)})

    return {
        "total": total, "average": round(total_stars / total, 2), "current": _tenths(current),
        "current_tenths": current, "zone": zone, "max": current >= 50,
        "target": target, "target_label": _tenths(target) if target else None,
        "target_zone": zone_of(target)["name"] if target else None,
        "targets": [{"value": t, "label": _tenths(t), "zone": zone_of(t)["name"]} for t in targets],
        "needed": needed, "pace": pace, "period": period, "period_name": PERIOD_NAMES[period],
        "plan": plan, "paces": paces, "growth": growth, "risk": risk,
        "lower_zone": ZONES[zone_index - 1][1] if zone_index > 0 else None,
        "scale": [{"key": k, "name": n, "range": f"{_tenths(lo)} a {_tenths(hi)}", "current": k == zone["key"],
                   "share": hi - lo + 1} for k, n, lo, hi in ZONES],
    }
