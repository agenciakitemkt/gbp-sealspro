"""Tipos e utilitarios compartilhados pelos itens."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from scoring import config
from scoring.curves import count_score


def status_for(score):
    if score is None:
        return "unavailable"
    if score < config.BAD_BELOW:
        return "bad"
    return "good" if score >= config.GOOD_AT else "fair"


def overall_status(score):
    """Faixa do medidor da nota geral (diferente do status de cada item)."""
    if score is None:
        return "unavailable"
    bands = config.OVERALL_BANDS
    return "bad" if score < bands["fair_from"] else "fair" if score <= bands["good_from"] else "good"


def overall_score(statuses):
    """Nota geral = piso de (bons*100 + razoaveis*50) / itens avaliados. Indisponiveis e itens que nao se aplicam
    ficam fora do total. Formula confirmada no original (10 locais da Completa e 54 da Pre Analise)."""
    w = config.OVERALL["weights"]
    total = sum(1 for st in statuses if st in w)
    if not total:
        return None
    return sum(w[st] for st in statuses if st in w) // total


def counters(items):
    """Contadores da nota geral, iguais na Completa e na Pre Analise."""
    count = lambda status: sum(1 for i in items if i["status"] == status)  # noqa: E731
    return {"score": overall_score([i["status"] for i in items]),
            "good": count("good"), "fair": count("fair"), "bad": count("bad"),
            "unavailable": count("unavailable"), "notApplicable": count("not_applicable")}


@dataclass(frozen=True)
class Outcome:
    score: int
    template: str
    vars: dict


@dataclass(frozen=True)
class Item:
    id: str                 # slug do contrato (secao 7)
    legacy_id: int          # id interno do original (secao 5)
    title: str
    requires: tuple         # secoes da coleta de que o item depende (nomes de collectionErrors)
    evaluate: Callable      # (perfil, now) -> Outcome
    applies: Callable = None            # (perfil) -> bool; None = sempre se aplica
    not_applicable_template: str = ""   # mensagem quando o item nao se aplica ao perfil


def present(ok, good_template, bad_template, vars=None):
    """Item binario: tem = 100, nao tem = config.BINARY_FAIL_SCORE."""
    return Outcome(100 if ok else config.BINARY_FAIL_SCORE, good_template if ok else bad_template, vars or {})


def count_item(item_id, current, good_template, low_template):
    c = config.CONFIG[item_id]
    score = count_score(current, c["recommended"], c.get("measured"))
    return Outcome(score, good_template if score == 100 else low_template,
                   {"current": current, "recommended": c["recommended"]})


def parse_dt(value):
    return datetime.fromisoformat(value)


def days_since(value, now):
    return max(0, (now - parse_dt(value)).days)
