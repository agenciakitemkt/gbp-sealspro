"""Utilitarios dos itens da Pre Analise. O tipo Item, o status e a nota geral vem de scoring/base.py (compartilhado)."""

from scoring.base import Outcome
from scoring.curves import count_score, step_score
from scoring.pre import config


def cfg(item_id):
    return config.CONFIG[item_id]


def binary(ok, good_template, bad_template, vars=None):
    return Outcome(100 if ok else 0, good_template if ok else bad_template, vars or {})


def floor_score(value, floors, below):
    """Curva 'quanto mais, melhor': a nota do primeiro `(minimo, nota)` atingido; abaixo de todos, `below`."""
    for minimum, score in sorted(floors, reverse=True):
        if value >= minimum:
            return score
    return below


def steps(item_id, value):
    c = cfg(item_id)
    return step_score(value, c["steps"], c["beyond"])


def count(item_id, value):
    c = cfg(item_id)
    return count_score(value, c["recommended"], c.get("measured"))


def by_score(score, good, fair, bad):
    """Escolhe o texto pela faixa da nota (100 = bom, 50 a 99 = razoavel, abaixo = fraco)."""
    return good if score == 100 else fair if score >= 50 else bad


def percent(part, whole):
    return round(100 * part / whole, 1)


def sample(profile):
    return profile["reviews"]["sample"]


def recent_window(profile):
    """(N, media das N mais recentes, media da amostra) para a tendencia.
    Amostra com `ratings` (notas da mais recente para a mais antiga, leitor da extensao): o motor calcula N pelo
    config. Sem `ratings` (adaptador do original): usa o que o original ja calculou, com a mesma regra de N."""
    s = sample(profile)
    ratings = s.get("ratings")
    if not ratings:
        return s["recentSize"], s["recentAverage"], s["average"]
    c = cfg("reviews_trend")
    n = min(len(ratings), max(c["recent_min"], (profile["reviews"].get("count") or 0) * c["recent_share"] // 100))
    return n, round(sum(ratings[:n]) / n, 2), round(sum(ratings) / len(ratings), 2)
