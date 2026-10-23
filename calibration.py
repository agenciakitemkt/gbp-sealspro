"""Fase 4: compara o motor de nota com respostas brutas da Analise Completa do GBP Check.

Os arquivos de referencia ficam em data/reference/*.json (fora do git). Dois formatos:

1) Um arquivo com varios locais (o que o GBP Check original gerou):
   {"fonte": ..., "avisos": [...], "ids_dos_itens": {"0": "Numero de telefone", ...},
    "locais": [{"name", "businessId", "analisadoHa", "overall", "counts": {"bad","fair","good"},
                "rating", "reviews", "starsDe1a5" (1 -> 5 estrelas), "scores": {legacyId: nota}}]}
   Item ausente em `scores` = nao se aplica ao local.

2) Formato antigo, um local por arquivo, com tolerancia: uma lista de itens com `id` (inteiro) e nota numerica
   (`score`, `nota`, `grade` ou `points`) e a nota geral num campo ao lado dessa lista ou acima dela.

Este modulo so le e compara: nao altera scoring/config.py.
"""

import difflib
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field

import storage
from collector.normalize import normalize
from scoring import analyze, config
from scoring.base import days_since, parse_dt

ITEM_SCORE_KEYS = ("score", "nota", "grade", "points")
OVERALL_KEYS = ("overallScore", "overall_score", "scoreGeral", "score_geral", "totalScore", "overall",
                "score", "nota", "total")
NAME_KEYS = ("locationName", "location_name", "businessName", "business_name", "name", "title")
FUZZY_MIN = 0.82
RECENT_MAX_DAYS = 14   # analise do original com ate 14 dias = recente; acima disso o perfil pode ter mudado
_AGE_UNITS = {"segundo": 1 / 86400, "minuto": 1 / 1440, "hora": 1 / 24, "dia": 1, "semana": 7, "mes": 30, "ano": 365}


# ---------------------------------------------------------------------------
# Leitura do arquivo de referencia
# ---------------------------------------------------------------------------

@dataclass
class Reference:
    path: str
    name: str = None                  # nome do local no arquivo (formato novo)
    names: list = field(default_factory=list)   # candidatos a nome do local, do mais ao menos confiavel
    items: dict = field(default_factory=dict)   # {id do original: nota}
    overall: float = None
    warnings: list = field(default_factory=list)
    business_id: str = None
    age_text: str = None              # "14 horas atras"
    age_days: float = None
    counts: dict = None               # {"bad", "fair", "good"} do original
    rating: float = None
    reviews: int = None
    stars: list = None                # 5 -> 1 estrelas (invertido a partir de starsDe1a5)
    item_names: dict = field(default_factory=dict)  # ids_dos_itens: {id: nome no original}

    @property
    def label(self):
        return self.name or os.path.basename(self.path)

    @property
    def recency(self):
        """'recente' | 'antiga' | 'desconhecida'."""
        if self.age_days is None:
            return "desconhecida"
        return "recente" if self.age_days <= RECENT_MAX_DAYS else "antiga"

    @property
    def keys(self):
        """Nomes aceitos em --map para este local."""
        base = os.path.basename(self.path)
        found = [base, os.path.splitext(base)[0]] + ([self.name, f"{base}#{self.name}"] if self.name else [])
        return {k.lower() for k in found}


def parse_age_days(text):
    """'14 horas atras' -> 0.58; '8 dias atras' -> 8; '1 mes atras' -> 30; None se nao entender."""
    if not isinstance(text, str):
        return None
    t = _norm(text)
    m = re.search(r"(\d+)\s*(segundo|minuto|hora|dia|semana|mes|ano)", t) \
        or re.search(r"\b(um|uma)\s+(segundo|minuto|hora|dia|semana|mes|ano)", t)
    if m:
        n = 1 if m.group(1) in ("um", "uma") else int(m.group(1))
        return n * _AGE_UNITS[m.group(2)]
    return 0 if "agora" in t else None


def _num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str) and re.fullmatch(r"\s*-?\d+(?:[.,]\d+)?\s*", value):
        number = float(value.replace(",", "."))
    else:
        return None
    return int(number) if float(number).is_integer() else number


def _item_id(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def _entry(entry):
    """(id, nota) de um item da lista, ou None se nao parecer um item."""
    if not isinstance(entry, dict):
        return None
    item_id = _item_id(entry.get("id"))
    score = next((_num(entry[k]) for k in ITEM_SCORE_KEYS if k in entry and _num(entry[k]) is not None), None)
    return None if item_id is None or score is None else (item_id, score)


def _item_lists(node, chain=()):
    """Todas as listas que parecem listas de itens, com a cadeia de dicionarios que as contem."""
    if isinstance(node, dict):
        for value in node.values():
            yield from _item_lists(value, chain + (node,))
    elif isinstance(node, list):
        entries = [e for e in map(_entry, node) if e]
        if entries:
            yield entries, chain
        for value in node:
            if isinstance(value, (dict, list)):
                yield from _item_lists(value, chain)


def _overall(chain):
    for container in reversed(chain):  # do mais proximo da lista para o topo
        for key in OVERALL_KEYS:
            value = container.get(key)
            if isinstance(value, dict):
                value = value.get("score", value.get("nota"))
            if _num(value) is not None:
                return _num(value)
    return None


def _names(node, depth=0):
    """Nomes candidatos em dicionarios (nao entra em listas: la ficam os titulos dos itens)."""
    if not isinstance(node, dict) or depth > 3:
        return []
    found = [str(node[k]).strip() for k in NAME_KEYS if isinstance(node.get(k), str) and node[k].strip()]
    for value in node.values():
        found += _names(value, depth + 1)
    return found


def parse_reference(data, path="referencia.json"):
    """Formato antigo: um local por arquivo."""
    ref = Reference(path=path)
    lists = list(_item_lists(data))
    if not lists:
        ref.warnings.append("nenhuma lista de itens com id e nota encontrada")
        return ref
    entries, chain = max(lists, key=lambda pair: len(pair[0]))
    for item_id, score in entries:
        if item_id in ref.items:
            ref.warnings.append(f"id {item_id} repetido; mantida a primeira nota")
        else:
            ref.items[item_id] = score
    ref.overall = _overall(chain)
    if ref.overall is None:
        ref.warnings.append("nota geral nao encontrada")
    stem = os.path.splitext(os.path.basename(path))[0].replace("_", " ").replace("-", " ")
    ref.names = list(dict.fromkeys(_names(data) + [stem]))
    return ref


def _parse_local(local, path, item_names):
    name = str(local.get("name") or "").strip() or None
    ref = Reference(path=path, name=name, names=[name] if name else [], item_names=item_names,
                    business_id=str(local["businessId"]) if local.get("businessId") not in (None, "") else None,
                    age_text=local.get("analisadoHa"), age_days=parse_age_days(local.get("analisadoHa")),
                    overall=_num(local.get("overall")), rating=_num(local.get("rating")),
                    reviews=_num(local.get("reviews")))
    for key, value in (local.get("scores") or {}).items():
        item_id, score = _item_id(key), _num(value)
        if item_id is None or score is None:
            ref.warnings.append(f"item '{key}' ignorado (id ou nota invalidos)")
        else:
            ref.items[item_id] = score
    counts = local.get("counts")
    if isinstance(counts, dict) and all(_num(counts.get(k)) is not None for k in ("bad", "fair", "good")):
        ref.counts = {k: _num(counts[k]) for k in ("bad", "fair", "good")}
    stars = local.get("starsDe1a5")
    if isinstance(stars, list) and len(stars) == 5 and all(_num(v) is not None for v in stars):
        ref.stars = [_num(v) for v in reversed(stars)]  # a tela mostra de 5 a 1 estrelas
    if ref.overall is None:
        ref.warnings.append("nota geral (overall) nao encontrada")
    if ref.age_days is None:
        ref.warnings.append("idade da analise desconhecida (campo analisadoHa): tratada com cautela")
    return ref


def parse_reference_file(data, path="referencia.json"):
    """-> (lista de Reference, meta). meta traz fonte, avisos e ids_dos_itens quando o arquivo os tem."""
    if isinstance(data, dict) and isinstance(data.get("locais"), list):
        item_names = {_item_id(k): v for k, v in (data.get("ids_dos_itens") or {}).items() if _item_id(k) is not None}
        refs = [_parse_local(l, path, item_names) for l in data["locais"] if isinstance(l, dict)]
        meta = {"fonte": data.get("fonte"), "avisos": [a for a in data.get("avisos") or [] if isinstance(a, str)],
                "item_names": item_names}
        return refs, meta
    return [parse_reference(data, path)], {"fonte": None, "avisos": [], "item_names": {}}


def load_reference(path):
    with open(path, encoding="utf-8") as f:
        return parse_reference(json.load(f), path)


def load_reference_file(path):
    with open(path, encoding="utf-8") as f:
        return parse_reference_file(json.load(f), path)


# ---------------------------------------------------------------------------
# Casamento referencia -> local
# ---------------------------------------------------------------------------

def _norm(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


@dataclass
class Match:
    location: object   # linha de `locations` ou None
    how: str


def _match_by_name(ref, locations):
    """Casa pelo nome (que no arquivo pode ser uma versao encurtada). Nunca chuta: ambiguidade vira 'sem casamento'."""
    by_id = {r["id"]: r for r in locations}
    for name in ref.names:
        if name in by_id:
            return Match(by_id[name], f"id {name}")
    titles = {r["id"]: _norm(r["title"]) for r in locations}
    for name in ref.names:
        n = _norm(name)
        exact = [r for r in locations if titles[r["id"]] == n]
        if len(exact) == 1:
            return Match(exact[0], f'nome igual a "{name}"')
    for name in ref.names:
        n = _norm(name)
        if len(n) < 5:
            continue
        hits = [r for r in locations if n in titles[r["id"]] or (len(titles[r["id"]]) >= 5 and titles[r["id"]] in n)]
        if len(hits) == 1:
            return Match(hits[0], f'nome contido: "{name}"')
        if len(hits) > 1:
            return Match(None, f'"{name}" casa com {len(hits)} locais: ' + "; ".join(h["title"] for h in hits[:4]))
    scored = sorted(((difflib.SequenceMatcher(None, _norm(name), titles[r["id"]]).ratio(), r)
                     for name in ref.names for r in locations), key=lambda pair: -pair[0])
    if scored and scored[0][0] >= FUZZY_MIN and (len(scored) == 1 or scored[1][1]["id"] == scored[0][1]["id"]
                                                  or scored[1][0] < scored[0][0] - 0.05):
        return Match(scored[0][1], f"nome parecido ({scored[0][0]:.0%})")
    near = ", ".join(dict.fromkeys(r["title"] for _, r in scored[:3]))
    return Match(None, f"sem casamento por nome (mais proximos: {near or 'nenhum'})")


def match_location(ref, locations):
    """Casamento por nome, conferido pelo businessId: no arquivo atual ele coincide com o id numerico do Google.

    - nome e businessId apontam para o mesmo local: confirmado;
    - apontam para locais diferentes: conflito, nao casa;
    - o nome nao casou (ou e ambiguo) mas o businessId coincide com um local: usa o businessId e avisa.
    """
    by_number = {r["id"].split("/")[-1]: r for r in locations}
    by_bid = by_number.get(ref.business_id) if ref.business_id else None
    match = _match_by_name(ref, locations)
    if match.location is not None:
        if by_bid is None:
            return match
        if by_bid["id"] != match.location["id"]:
            return Match(None, f"conflito: o nome aponta para {match.location['title']} e o businessId para "
                               f"{by_bid['title']}")
        return Match(match.location, match.how + "; businessId confere")
    if by_bid is not None:
        return Match(by_bid, f"businessId coincide com o id do Google ({match.how})")
    return match


# ---------------------------------------------------------------------------
# Comparacao
# ---------------------------------------------------------------------------

@dataclass
class Row:
    id: int
    title: str
    original: object   # nota do original ou None (item que nao se aplica / so no motor)
    engine: object     # nota do motor ou None (indisponivel, nao se aplica ou so no original)
    note: str = ""     # so no original | so no motor | indisponivel | nao se aplica nos dois

    @property
    def diff(self):
        return None if self.original is None or self.engine is None else self.engine - self.original


@dataclass
class Comparison:
    ref: Reference
    location_title: str
    collected_at: str
    rows: list
    overall_original: object
    overall_engine: object
    overall_engine_same_items: object   # motor, so com os itens que o original tem
    counts_engine: dict                 # {"bad", "fair", "good"} do motor
    formula_original: object            # a formula do motor aplicada aos contadores do original
    profile_checks: list                # [(rotulo, original, motor)] de avaliacoes, nota media e estrelas
    engine_items: dict = field(default_factory=dict)   # {legacyId: item do motor}
    raw: dict = None                    # valores brutos da coleta (ver raw_values)

    @property
    def overall_diff(self):
        return None if self.overall_original is None or self.overall_engine is None \
            else self.overall_engine - self.overall_original


def _mean(values):
    values = list(values)
    return round(sum(values) / len(values), 2) if values else None


def formula_overall(counts):
    """Nota geral do original recalculada a partir dos contadores: piso de (bons*100 + razoaveis*50) / total."""
    total = counts["good"] + counts["fair"] + counts["bad"]
    return (counts["good"] * 100 + counts["fair"] * 50) // total if total else None


def _same(a, b):
    if isinstance(a, list) or isinstance(b, list):
        return a == b
    return abs(a - b) < 0.05


def raw_values(profile, now):
    """Valores brutos que os itens 19, 29 e 30 usam, para conferir a divergencia a olho."""
    posts = [p["createdAt"] for p in profile["posts"] if p.get("createdAt")]
    min_year = config.CONFIG["last_owner_media"]["ignore_before_year"]
    own = [m["createdAt"] for m in profile["media"]
           if m.get("createdAt") and parse_dt(m["createdAt"]).year >= min_year]
    unanswered = [r for r in profile["reviews"] if not r["replied"]]
    return {"posts": len(posts), "post_date": max(posts)[:10] if posts else None,
            "post_days": days_since(max(posts), now) if posts else None,
            "media_dated": len(own), "media_date": max(own)[:10] if own else None,
            "media_days": days_since(max(own), now) if own else None,
            "reviews": len(profile["reviews"]), "unanswered": len(unanswered),
            "unanswered_ages": sorted(days_since(r["createdAt"], now) for r in unanswered)}


def compare(ref, result, location_title="", collected_at="", profile=None):
    engine = {i["legacyId"]: i for i in result["items"]}
    rows = []
    for item_id in sorted(set(ref.items) | set(engine)):
        item = engine.get(item_id)
        original = ref.items.get(item_id)
        title = item["title"] if item else ref.item_names.get(item_id, "(item fora do catalogo do motor)")
        if item is None:
            note, score = "so no original", None
        elif item["status"] == "not_applicable":
            note, score = ("nao se aplica nos dois" if original is None else "so no original"), None
        elif original is None:
            note, score = "so no motor", item["score"]
        else:
            note, score = ("indisponivel" if item["score"] is None else ""), item["score"]
        rows.append(Row(item_id, title, original, score, note))
    same = [engine[i]["score"] for i in ref.items if i in engine and engine[i]["score"] is not None]
    o, loc = result["overall"], result["location"]
    checks = []
    if ref.reviews is not None:
        checks.append(("avaliacoes", ref.reviews, loc["reviewCount"]))
    if ref.rating is not None:
        checks.append(("nota media", ref.rating, loc["rating"]))
    if ref.stars is not None:
        checks.append(("estrelas 5 a 1", ref.stars, loc["starDistribution"]))
    from datetime import datetime
    raw = raw_values(profile, datetime.fromisoformat(result["analyzedAt"])) if profile else None
    return Comparison(ref, location_title, collected_at, rows, ref.overall, o["score"], _mean(same),
                      {"bad": o["bad"], "fair": o["fair"], "good": o["good"]},
                      formula_overall(ref.counts) if ref.counts else None, checks, engine, raw)


def summarize(comparisons, top=5):
    """Itens com divergencia, do mais divergente (media do desvio absoluto) para o menos."""
    stats = {}
    for c in comparisons:
        for row in c.rows:
            entry = stats.setdefault(row.id, {"id": row.id, "title": row.title, "diffs": [], "files": [],
                                              "compared": 0, "only_one_side": 0})
            if row.diff is None:
                entry["only_one_side"] += row.note in ("so no original", "so no motor")
                continue
            entry["compared"] += 1
            entry["diffs"].append(row.diff)
            if row.diff != 0:
                entry["files"].append((c.ref.label, c.ref.recency, row.original, row.engine, row.diff))
    ranked = []
    for entry in stats.values():
        if not entry["files"] and not entry["only_one_side"]:
            continue
        diffs = entry["diffs"]
        entry["mean_abs"] = _mean(abs(d) for d in diffs) or 0
        entry["max_abs"] = max((abs(d) for d in diffs), default=0)
        entry["wrong"] = len(entry["files"])
        ranked.append(entry)
    ranked.sort(key=lambda e: (-e["mean_abs"], -e["max_abs"], -e["only_one_side"], e["id"]))
    return ranked[:top]


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------

def _fmt(value, signed=False):
    if value is None:
        return "-"
    return f"{value:+g}" if signed and value != 0 else f"{value:g}"


def _age_line(ref):
    if ref.recency == "recente":
        return f"Idade da analise do original: {ref.age_text} (RECENTE: dados comparaveis com a coleta)"
    if ref.recency == "antiga":
        return (f"Idade da analise do original: {ref.age_text} (ANTIGA: o perfil pode ter mudado desde entao; "
                f"trate as diferencas com cautela)")
    return "Idade da analise do original: desconhecida (trate as diferencas com cautela)"


def render_comparison(c):
    lines = [f"=== {c.ref.label} -> {c.location_title} (coleta de {c.collected_at[:10]}) ===", _age_line(c.ref),
             f"{'id':>3}  {'item':<42} {'original':>8} {'motor':>6} {'dif':>5}",
             "-" * 70]
    for r in c.rows:
        flag = "  *" if r.diff not in (None, 0) else ""
        engine = "indisp." if r.note == "indisponivel" else _fmt(r.engine)
        note = f"  ({r.note})" if r.note in ("so no original", "so no motor", "nao se aplica nos dois") else ""
        lines.append(f"{r.id:>3}  {r.title[:42]:<42} {_fmt(r.original):>8} {engine:>6} "
                     f"{_fmt(r.diff, True) if r.diff is not None else '-':>5}{flag}{note}")
    lines += ["-" * 70,
              f"Nota geral: original {_fmt(c.overall_original)} | motor {_fmt(c.overall_engine)} | "
              f"dif {_fmt(c.overall_diff, True)}"]
    if c.ref.counts:
        o = c.ref.counts
        e = c.counts_engine
        lines.append(f"  contadores (fraco/razoavel/bom): original {o['bad']}/{o['fair']}/{o['good']} | "
                     f"motor {e['bad']}/{e['fair']}/{e['good']}")
        if c.formula_original is not None and c.overall_original is not None:
            ok = "confere" if c.formula_original == c.overall_original else f"NAO confere (original {_fmt(c.overall_original)})"
            lines.append(f"  formula (bons*100 + razoaveis*50) / total aplicada aos contadores do original: "
                         f"{c.formula_original} -> {ok}")
    if c.overall_engine_same_items is not None and c.overall_engine_same_items != c.overall_engine:
        lines.append(f"  media do motor so com os itens que o original tem: {_fmt(c.overall_engine_same_items)}")
    for label, original, engine in c.profile_checks:
        mark = "ok" if _same(original, engine) else "DIFERE"
        lines.append(f"  {label}: original {original} | coleta {engine} -> {mark}")
    for w in c.ref.warnings:
        lines.append(f"  aviso: {w}")
    return "\n".join(lines)


def _detail_lines(ranked):
    lines = []
    for e in ranked:
        lines.append(f"  [{e['id']:>2}] {e['title']}: diverge em {e['wrong']} de {e['compared']} "
                     f"comparacoes (desvio medio {e['mean_abs']:g}, maximo {e['max_abs']:g})"
                     + (f"; {e['only_one_side']} so em um dos lados" if e["only_one_side"] else ""))
        for label, recency, original, engine, diff in e["files"]:
            tag = "" if recency == "recente" else f" [{recency}]"
            lines.append(f"        {label[:34]}{tag}: original {_fmt(original)} -> motor {_fmt(engine)} ({_fmt(diff, True)})")
    return lines


def render_summary(comparisons, skipped, top=5, unreferenced=()):
    recent = [c for c in comparisons if c.ref.recency == "recente"]
    lines = ["", "=" * 70, f"RESUMO: {len(comparisons)} local(is) comparado(s) ({len(recent)} com analise recente)"
             + (f", {len(skipped)} ignorado(s)" if skipped else "")]
    overall = [c for c in comparisons if c.overall_diff is not None]
    if overall:
        lines.append("Nota geral (original x motor):")
        for c in overall:
            lines.append(f"  {c.ref.label[:34]:<34} {c.ref.recency:<12} original {_fmt(c.overall_original):>4}  "
                         f"motor {_fmt(c.overall_engine):>4}  dif {_fmt(c.overall_diff, True):>4}")
        ro = [c for c in overall if c.ref.recency == "recente"]
        if ro:
            lines.append(f"  desvio medio absoluto, so analises recentes ({len(ro)}): {_mean(abs(c.overall_diff) for c in ro):g}")
        lines.append(f"  desvio medio absoluto, todas ({len(overall)}, as antigas pesam menos como evidencia): "
                     f"{_mean(abs(c.overall_diff) for c in overall):g}")
    formula = [c for c in comparisons if c.formula_original is not None and c.overall_original is not None]
    if formula:
        ok = sum(c.formula_original == c.overall_original for c in formula)
        lines.append(f"Formula da nota geral aplicada aos contadores do original: confere em {ok} de {len(formula)} locais.")

    ranked_recent = summarize(recent, top)
    lines.append(f"Itens com maior divergencia nas analises RECENTES (maior confianca; {len(recent)} local(is)):")
    lines += _detail_lines(ranked_recent) if ranked_recent else ["  nenhuma divergencia nas analises recentes."]
    ranked_all = summarize(comparisons, top)
    lines.append("Itens com maior divergencia em TODAS as analises (as [antiga] podem refletir mudancas no perfil "
                 "depois da analise do original):")
    lines += _detail_lines(ranked_all) if ranked_all else ["  nenhuma divergencia."]
    if unreferenced:
        lines.append("Locais ativos sem referencia no arquivo (nada a comparar): " + "; ".join(unreferenced))
    if skipped:
        lines.append("Ignorados:")
        lines += [f"  {label}: {why}" for label, why in skipped]
    lines.append("O config nao foi alterado.")
    return "\n".join(lines)


_DATE_RE = re.compile(r"[_\-\s]?(\d{4}-\d{2}-\d{2})")


def select_reference_files(names):
    """Arquivos da mesma familia (mesmo nome, com ou sem data) sao versoes: vale a de data mais recente.

    `gbpcheck_original.json` e `gbpcheck_original_2026-10-08.json` sao a mesma familia; sem data = mais antigo.
    Devolve (principais, historico).
    """
    families = {}
    for name in names:
        stem = os.path.splitext(name)[0]
        m = _DATE_RE.search(stem)
        families.setdefault(_DATE_RE.sub("", stem, count=1).lower(), []).append((m.group(1) if m else "", name))
    used, history = [], []
    for files in families.values():
        files.sort()
        used.append(files[-1][1])
        history += [n for _, n in files[:-1]]
    return sorted(used), sorted(history)


def _item_text(c, item_id):
    item = c.engine_items.get(item_id)
    if not item:
        return ""
    return item["message"]["template"].format(**{k: v for k, v in item["message"]["vars"].items()})


def _raw_note(c, item_id):
    """Valores brutos usados pelo motor nos itens 19, 29 e 30; nos demais, a situacao atual do item."""
    r = c.raw
    if r is None:
        return _item_text(c, item_id)
    if item_id == 19:
        ages = r["unanswered_ages"]
        return (f"{r['unanswered']} sem resposta de {r['reviews']} avaliacoes"
                + (f"; idade (dias) das sem resposta: {ages[:12]}{'...' if len(ages) > 12 else ''}" if ages else ""))
    if item_id == 29:
        return (f"ultima postagem ha {r['post_days']} dias ({r['post_date']}); {r['posts']} postagens"
                if r["posts"] else "nenhuma postagem")
    if item_id == 30:
        return (f"ultima midia do proprietario ha {r['media_days']} dias ({r['media_date']}); "
                f"{r['media_dated']} midias com data valida" if r["media_dated"] else "nenhuma midia com data valida")
    return _item_text(c, item_id)


def render_divergences(comparisons):
    """Por local e item: onde o motor ainda diverge do original, com os valores brutos usados."""
    lines = ["", "=" * 70, "DIVERGENCIAS POR LOCAL (so os itens em que motor e original diferem)"]
    for c in comparisons:
        bad = [r for r in c.rows if r.diff not in (None, 0) or r.note in ("so no original", "so no motor")]
        lines.append(f"\n{c.ref.label} [{c.ref.recency}, {c.ref.age_text}] -> nota geral original "
                     f"{_fmt(c.overall_original)} | motor {_fmt(c.overall_engine)} | dif {_fmt(c.overall_diff, True)}")
        if not bad:
            lines.append("  nenhum item diverge")
        for r in bad:
            tag = f" ({r.note})" if r.note in ("so no original", "so no motor") else ""
            lines.append(f"  [{r.id:>2}] {r.title}: original {_fmt(r.original)} -> motor {_fmt(r.engine)} "
                         f"({_fmt(r.diff, True)}){tag}")
            lines.append(f"        valores usados: {_raw_note(c, r.id)}")
    with_raw = [c for c in comparisons if c.raw]
    if with_raw:
        lines += ["", "VALORES BRUTOS DOS ITENS 19, 29 E 30 EM TODOS OS LOCAIS (original/motor entre parenteses)",
                  f"{'local':<28} {'19 sem resp/total':>18} {'(orig/motor)':>13} {'29 dias':>8} {'(orig/motor)':>13} "
                  f"{'30 dias':>8} {'(orig/motor)':>13}"]
        for c in with_raw:
            rows = {r.id: r for r in c.rows}
            pair = lambda i: f"({_fmt(rows[i].original)}/{_fmt(rows[i].engine)})" if i in rows else "-"  # noqa: E731
            r = c.raw
            lines.append(f"{c.ref.label[:28]:<28} {str(r['unanswered']) + '/' + str(r['reviews']):>18} {pair(19):>13} "
                         f"{_fmt(r['post_days']):>8} {pair(29):>13} {_fmt(r['media_days']):>8} {pair(30):>13}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orquestracao (usada pelo comando `coletar.py calibrar`)
# ---------------------------------------------------------------------------

def reference_dir():
    return os.path.join(storage.DATA, "reference")


def calibrate(db, directory=None, manual=None, top=5, out=print, include_history=False, only_divergences=False):
    """Roda a comparacao. `manual` = {nome do arquivo, do local ou 'arquivo#local': linha de `locations`}.

    Entre versoes do mesmo arquivo (com data no nome) usa so a mais recente; as outras ficam como historico
    (`include_history=True` compara tambem). `only_divergences=True` imprime so as divergencias e o resumo.
    """
    directory = directory or reference_dir()
    manual = {k.lower(): v for k, v in (manual or {}).items()}
    names = [f for f in sorted(os.listdir(directory)) if f.lower().endswith(".json")] if os.path.isdir(directory) else []
    if not names:
        out(f"Nenhum arquivo .json em {directory}\n"
            "Coloque ali a resposta bruta da Analise Completa do GBP Check "
            "(um arquivo com a lista \"locais\", ou um arquivo por local com itens e nota).")
        return []
    used, history = (names, []) if include_history else select_reference_files(names)
    if history:
        out(f"Referencia principal: {', '.join(used)}")
        out(f"Historico (nao usado; --incluir-historico para comparar tambem): {', '.join(history)}")
        out("")
    locations = storage.list_locations(db)
    comparisons, skipped, matched_ids = [], [], set()
    for name in used:
        try:
            refs, meta = load_reference_file(os.path.join(directory, name))
        except (OSError, ValueError) as e:
            skipped.append((name, f"nao foi possivel ler ({e.__class__.__name__}: {e})"))
            continue
        out(f"##### {name}: {len(refs)} local(is)" + (f" | fonte: {meta['fonte']}" if meta.get("fonte") else ""))
        for aviso in meta.get("avisos", []):
            out(f"  aviso do arquivo: {aviso}")
        out("")
        for ref in refs:
            if not ref.items:
                skipped.append((ref.label, "; ".join(ref.warnings) or "sem itens"))
                continue
            forced = next((manual[k] for k in ref.keys if k in manual), None)
            match = Match(forced, "ajuste manual") if forced else match_location(ref, locations)
            if match.location is None:
                skipped.append((ref.label, f"{match.how}. Use --map \"{ref.label}\"=<locations/ID ou parte do nome>"))
                continue
            raw = storage.latest_raw(match.location["id"])
            if raw is None:
                skipped.append((ref.label, f"{match.location['title']} nao tem coleta guardada; "
                                           f"rode: coletar.py coletar \"{match.location['id']}\""))
                continue
            profile = normalize(raw)
            result = analyze(profile)
            c = compare(ref, result, match.location["title"], raw["collectedAt"], profile)
            matched_ids.add(match.location["id"])
            if not only_divergences:
                out(f"[{ref.label}] casado com {match.location['title']} ({match.how})")
                out(render_comparison(c))
                out("")
            else:
                out(f"[{ref.label}] casado com {match.location['title']} ({match.how}); "
                    f"coleta de {raw['collectedAt'][:16]}")
            comparisons.append(c)
    if only_divergences:
        out(render_divergences(comparisons))
    unreferenced = [r["title"] for r in storage.list_locations(db, only_active=True) if r["id"] not in matched_ids]
    out(render_summary(comparisons, skipped, top, unreferenced))
    if not only_divergences:
        out(render_divergences(comparisons))
    return comparisons
