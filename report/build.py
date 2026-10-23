"""Dados do relatorio do cliente. Usa so analises REAIS (nunca retroativas) e nunca texto de avaliacoes."""

import re
import unicodedata

import history
import storage
from report import texts
from scoring import config, version
from scoring.base import overall_status
from web import format as fmt


class ReportError(Exception):
    """Nao da para gerar o relatorio agora. A mensagem pode ser mostrada ao usuario."""


def slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "local"


def _day(iso):
    return fmt.local_datetime(iso)[:10]


def _file_day(iso):
    """Data local (Brasilia) no formato AAAA-MM-DD, a mesma que aparece no relatorio."""
    d, m, y = _day(iso).split("/")
    return f"{y}-{m}-{d}"


def is_current_version(analysis):
    return (analysis["engine_version"] == version.ENGINE_VERSION
            and analysis["config_hash"] == version.config_hash())


def _item_texts(item):
    """(titulo, situacao, orientacao, tipo). Se uma analise antiga trouxer variaveis diferentes, cai no texto guardado."""
    try:
        return texts.describe(item["id"], item["status"], item["message"]["vars"])
    except (KeyError, TypeError, ValueError):
        return (texts.TITLES.get(item["id"], item["title"]), fmt.render_message(item["message"]), "", "fazer")


def evolution(db, location_id, since=None, until=None):
    """Pontos da evolucao: so analises reais da versao atual do motor e do config, entre `since` e `until`
    (analyzed_at, inclusive; None = sem limite).

    A secao so existe com analises em pelo menos 2 datas diferentes (data de Brasilia): varias analises no mesmo dia
    nao mostram evolucao nenhuma e a secao e omitida.
    """
    eligible = [a for a in storage.list_analyses(db, location_id)
                if a["kind"] == "real" and is_current_version(a) and a["score"] is not None
                and (since is None or a["analyzed_at"] >= since) and (until is None or a["analyzed_at"] <= until)]
    if len({_day(a["analyzed_at"]) for a in eligible}) < 2:
        return None
    chart = history.build_chart(eligible, width=720, height=280)
    first, last = eligible[0], eligible[-1]
    delta = last["score"] - first["score"]
    verb = "subiu" if delta > 0 else "caiu" if delta < 0 else "se manteve"
    d1, d2 = _day(first["analyzed_at"]), _day(last["analyzed_at"])
    if delta:
        sentence = f"A nota geral {verb} de {first['score']} ({d1}) para {last['score']} ({d2})."
    else:
        sentence = f"A nota geral se manteve em {last['score']} entre {d1} e {d2}."
    for p in chart["points"]:
        p["date"] = _day(p["analyzed_at"])
    for xl in chart["xlabels"]:
        xl["date"] = _day(xl["analyzed_at"])
    return {"chart": chart, "sentence": sentence, "count": len(eligible)}


def real_analysis(db, location_id, analysis_id):
    """Analise REAL guardada do local. ReportError se nao existir, for de outro local ou for retroativa."""
    analysis = storage.get_analysis(db, analysis_id)
    if analysis is None or analysis["location_id"] != location_id:
        raise ReportError("Análise não encontrada para este local.")
    if analysis["kind"] != "real":
        raise ReportError("Esta análise foi calculada depois, a partir de uma coleta antiga, e não entra no relatório. "
                          "Escolha uma análise real.")
    return analysis


def build_report(db, location_id, summary=False, analysis_id=None):
    """Relatorio da ultima analise real do local ou, com `analysis_id`, de uma analise real do historico. A evolucao
    vai so ate a data da analise escolhida."""
    if analysis_id is None:
        analysis = storage.latest_analysis(db, location_id)  # so analises reais
        if analysis is None:
            raise ReportError("Este local ainda não tem uma análise real. Clique em Analisar antes de gerar o relatório.")
    else:
        analysis = real_analysis(db, location_id, analysis_id)
    result, overall = analysis["result"], analysis["result"]["overall"]
    if overall["score"] is None:
        raise ReportError("Nenhum item pôde ser avaliado nesta análise. Refaça a análise antes de gerar o relatório.")

    evaluated, skipped = [], []
    for item in result["items"]:  # o motor ja entrega do pior para o melhor, sem nota por ultimo
        if item["status"] in ("good", "fair", "bad"):
            title, situation, advice, kind = _item_texts(item)
            evaluated.append({"id": item["id"], "status": item["status"], "status_name": texts.STATUS_NAME[item["status"]],
                              "title": title, "situation": situation, "advice": advice, "advice_kind": kind,
                              "marker": round(fmt.band_position(item["score"]), 1)})
        else:
            skipped.append({"title": texts.TITLES.get(item["id"], item["title"]),
                            "reason": texts.NOT_APPLICABLE if item["status"] == "not_applicable" else texts.UNAVAILABLE})
    counts = {k: overall[k] for k in ("good", "fair", "bad")}
    status = overall_status(overall["score"])
    first, second = texts.overall_sentences(status, counts)
    warnings = []
    if overall["unavailable"]:
        n = overall["unavailable"]
        warnings.append(f"{n} {'item não pôde' if n == 1 else 'itens não puderam'} ser avaliado(s) por falha na coleta "
                        "e ficam fora da nota.")
    if not is_current_version(analysis):
        warnings.append("Esta análise foi feita com uma versão anterior dos critérios de avaliação. "
                        "Clique em Analisar de novo para atualizar antes de entregar.")
    loc = result["location"]
    return {
        "location": loc, "analysis_id": analysis["id"], "date": _day(analysis["analyzed_at"]),
        "overall": overall, "status": status, "status_name": texts.STATUS_NAME[status],
        "counts": counts, "sentence_1": first, "sentence_2": second,
        "groups": [{"status": s, "name": texts.STATUS_NAME[s], "help": texts.STATUS_HELP[s],
                    "items": [i for i in evaluated if i["status"] == s]}
                   for s in ("bad", "fair", "good") if any(i["status"] == s for i in evaluated)],
        "skipped": skipped, "evolution": evolution(db, location_id, until=analysis["analyzed_at"]), "warnings": warnings,
        "bands": config.OVERALL_BANDS, "summary": summary,
        "filename": f"Relatorio-{'Resumo-' if summary else ''}{slug(loc['name'])}-{_file_day(analysis['analyzed_at'])}.pdf",
    }
