"""Pre Analise, Fase 0: compara o motor da Pre (scoring/pre) com as pre analises guardadas no GBP Check original.

Le data/reference/pre_analises_original.json (fora do git): uma lista de casos, cada um com as notas do original por
item (`items`: id, s), os totais (`stats`: overall_score, good_items, fair_items, bad_items) e os dados brutos que ele
usou (`pd`). O `pd` passa pelo adaptador (collector_pre/from_original.py) e o motor roda sobre o perfil normalizado.

Tudo offline: nao coleta nada e nao altera scoring/pre/config.py.
"""

import json
import os
from dataclasses import dataclass, field

import storage
from collector_pre.from_original import to_profile
from scoring.base import counters, status_for
from scoring.pre import analyze
from scoring.pre.engine import missing_groups
from scoring.pre.items import ITEMS
from scoring.pre.version import PRE_ENGINE_VERSION, config_hash

REFERENCE_FILE = "pre_analises_original.json"
# Grupos que tiramos da nota por decisao nossa, onde o original pontua: sem concorrentes ele da 100 (CLAUDE.md, 12.4).
DECISIONS = {"competitors": "sem concorrentes: o original da 100, aqui fica fora da nota"}
TITLES = {item.legacy_id: item.title for item in ITEMS}
GROUP_OF = {item.legacy_id: item.requires[0] if item.requires else None for item in ITEMS}


@dataclass
class ItemRow:
    original_id: str
    title: str
    original: int = None      # nota do original (None = o original deixou fora)
    engine: int = None        # nota do motor (None = fora da nota)
    vars: dict = field(default_factory=dict)
    decision: str = None      # motivo, quando a diferenca e decisao nossa

    @property
    def same(self):
        return self.original == self.engine


@dataclass
class CaseResult:
    name: str
    original: dict            # {"score", "good", "fair", "bad"}
    engine: dict
    as_original: dict         # motor, mas contando como o original os itens que tiramos por decisao
    rows: list

    @property
    def totals_match(self):
        return _totals(self.original) == _totals(self.engine)

    @property
    def totals_match_as_original(self):
        return _totals(self.original) == _totals(self.as_original)

    @property
    def rule_divergences(self):
        return [r for r in self.rows if not r.same and not r.decision]

    @property
    def decision_rows(self):
        return [r for r in self.rows if not r.same and r.decision]


def _totals(o):
    return (o["score"], o["good"], o["fair"], o["bad"])


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("casos") or data.get("analises") or []


def compare_case(case):
    profile = to_profile(case)
    result = analyze(profile)
    missing = missing_groups(profile)
    orig = {i["id"]: i["s"] for i in case["items"]}
    ours = {i["originalId"]: i for i in result["items"]}
    rows, as_original = [], []
    for oid in [item.legacy_id for item in ITEMS]:
        mine = ours[oid]
        group = GROUP_OF[oid]
        decision = DECISIONS.get(group) if mine["score"] is None and group in missing and orig.get(oid) is not None \
            else None
        rows.append(ItemRow(oid, TITLES[oid], orig.get(oid), mine["score"], mine["message"]["vars"], decision))
        as_original.append({"status": status_for(orig[oid]) if decision else mine["status"]})
    st = case["stats"]
    return CaseResult(
        name=(case.get("basic") or {}).get("location_name") or profile["location"]["name"],
        original={"score": st["overall_score"], "good": st["good_items"], "fair": st["fair_items"],
                  "bad": st["bad_items"]},
        engine=result["overall"], as_original=counters(as_original), rows=rows)


# ---------------------------------------------------------------------------
# Relatorio
# ---------------------------------------------------------------------------

def _fmt(v):
    return "fora" if v is None else str(v)


def _totals_text(o):
    return f"{_fmt(o['score'])} ({o['good']} bons, {o['fair']} razoaveis, {o['bad']} fracos)"


def _vars_text(vars_):
    return ", ".join(f"{k}={v}" for k, v in vars_.items() if k != "sections") or "-"


def summarize_items(results):
    """Por item: (iguais, comparados, so por decisao nossa, divergencias de regra)."""
    out = {}
    for item in ITEMS:
        rows = [next(r for r in c.rows if r.original_id == item.legacy_id) for c in results]
        compared = [r for r in rows if r.original is not None or r.engine is not None]
        out[item.legacy_id] = (sum(r.same for r in compared), len(compared),
                               sum(1 for r in compared if r.decision), sum(1 for r in compared if not r.same and not r.decision))
    return out


def render(results, path, only_divergences=False):
    n = len(results)
    lines = [f"PRE ANALISE: motor contra o original ({os.path.basename(path)}, {n} casos)",
             f"Motor da Pre: versao {PRE_ENGINE_VERSION}, config {config_hash()[:12]}", ""]
    if not only_divergences:
        lines.append(f"{'caso':<40} {'itens':>5}  {'original':<34} {'motor':<34}")
        for c in results:
            evaluated = sum(1 for r in c.rows if r.engine is not None)
            mark = "" if c.totals_match else "  <- diferente"
            lines.append(f"{c.name[:40]:<40} {evaluated:>5}  {_totals_text(c.original):<34} {_totals_text(c.engine):<34}{mark}")
        lines.append("")

    lines.append("DIVERGENCIAS POR CASO (itens em que motor e original diferem)")
    any_case = False
    for c in results:
        if c.totals_match and not c.rule_divergences and not c.decision_rows:
            continue
        any_case = True
        lines.append(f"\n{c.name}: original {_totals_text(c.original)} | motor {_totals_text(c.engine)}")
        for r in c.rule_divergences:
            lines.append(f"  [regra]   {r.title} ({r.original_id}): original {_fmt(r.original)} -> motor {_fmt(r.engine)}")
            lines.append(f"            valores: {_vars_text(r.vars)}")
        for r in c.decision_rows:
            lines.append(f"  [decisao] {r.title} ({r.original_id}): original {_fmt(r.original)} -> motor fora da nota "
                         f"({r.decision})")
        if c.decision_rows:
            tag = "igual ao original" if c.totals_match_as_original else "ainda diferente"
            lines.append(f"  contando esses itens como o original: {_totals_text(c.as_original)}, {tag}")
    if not any_case:
        lines.append("  nenhum caso diverge")

    lines += ["", "POR ITEM (notas iguais / casos comparados; fora da nota por decisao nossa; divergencias de regra)"]
    for oid, (same, compared, decided, rule) in summarize_items(results).items():
        extra = (f"; {decided} por decisao" if decided else "") + (f"; {rule} DIVERGEM" if rule else "")
        lines.append(f"  {TITLES[oid][:44]:<44} {same:>3}/{compared}{extra}")

    totals = sum(c.totals_match for c in results)
    as_orig = sum(c.totals_match_as_original for c in results)
    rule_items = sum(len(c.rule_divergences) for c in results)
    decided = sum(1 for c in results if c.decision_rows)
    compared = sum(1 for c in results for r in c.rows if r.original is not None or r.engine is not None)
    same = sum(1 for c in results for r in c.rows if (r.original is not None or r.engine is not None) and r.same)
    lines += ["", "RESUMO",
              f"  Nota geral e contadores iguais ao original: {totals} de {n}",
              f"  Contando como o original os itens que tiramos por decisao: {as_orig} de {n}"
              + (f" ({decided} casos com item fora da nota por decisao nossa)" if decided else ""),
              f"  Itens com nota igual: {same} de {compared}; divergencias de regra: {rule_items}",
              f"  Aceite (CLAUDE.md, 12.10): 0 divergencias de regra e {n} de {n} contando como o original os itens "
              "tirados por decisao nossa: " + ("atingido" if rule_items == 0 and as_orig == n else "NAO atingido"),
              "  Lembrete: as regras foram montadas com estes mesmos 54 casos; reproduzir aqui e ajuste, nao validacao."]
    return "\n".join(lines)


def reference_path(path=None):
    return path or os.path.join(storage.DATA, "reference", REFERENCE_FILE)


def calibrate_pre(path=None, only_divergences=False, out=print):
    path = reference_path(path)
    if not os.path.exists(path):
        out(f"Arquivo de referencia nao encontrado: {path}")
        return []
    results = [compare_case(c) for c in load_cases(path)]
    out(render(results, path, only_divergences))
    return results
