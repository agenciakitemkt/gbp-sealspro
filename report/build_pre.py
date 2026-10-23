"""Dados do PDF da Pre Analise (CLAUDE.md, secao 12). Usa a pre analise guardada, sem reavaliar; nunca texto de
avaliacoes (a analise guardada nem tem). O mesmo modelo HTML da Completa (report/templates/relatorio.html)."""

import storage
from report import texts_pre as texts
from report.build import ReportError, _day, _file_day, slug
from scoring import config
from scoring.base import overall_status
from scoring.pre import version
from web import format as fmt

MISSING_ALERT = 3  # a partir de quantos itens nao avaliados a tela /pre ja manda conferir antes de usar com cliente


def is_current_version(analysis):
    return (analysis["engine_version"] == version.PRE_ENGINE_VERSION
            and analysis["config_hash"] == version.config_hash())


def _competitors(items):
    """Resumo dos concorrentes, a partir dos itens 'top 10' e 'acima da media' (None se nao foram avaliados)."""
    by_id = {i["id"]: i for i in items if i["status"] in ("good", "fair", "bad")}
    top, avg = by_id.get("top10_reviews"), by_id.get("above_segment_average")
    if not top or not avg:
        return None
    v = avg["message"]["vars"]
    return {"count": v["competitors"], "average": round(v["average"]), "reviews": v["current"],
            "top10": top["status"] == "good", "above": avg["status"] == "good"}


def warnings_for(analysis):
    """Avisos para quem gera o PDF (tela e linha de comando), nunca impressos no relatorio."""
    result, out = analysis["result"], []
    n = result["overall"]["unavailable"]
    if n >= MISSING_ALERT:
        out.append(f"Faltam {n} de {len(result['items'])} itens: a nota considera só os avaliados e pode mudar. "
                   "Confira antes de entregar.")
    elif n:
        out.append(f"{n} {'item não pôde' if n == 1 else 'itens não puderam'} ser avaliado(s) e ficam fora da nota.")
    if analysis["warnings"]:
        out.append("A coleta teve avisos (veja na tela da pré análise).")
    if not is_current_version(analysis):
        out.append("Esta pré análise foi feita com uma versão anterior dos critérios. Refaça a pré análise "
                   "antes de entregar.")
    return out


def build_pre_report(db, analysis_id, summary=False):
    analysis = storage.get_pre_analysis(db, analysis_id)
    if analysis is None:
        raise ReportError("Pré análise não encontrada.")
    result, overall = analysis["result"], analysis["result"]["overall"]
    if overall["score"] is None:
        raise ReportError("Nenhum item pôde ser avaliado nesta pré análise. Refaça a pré análise antes de gerar o PDF.")

    evaluated, skipped = [], []
    for item in result["items"]:  # o motor ja entrega do pior para o melhor, sem nota por ultimo
        if item["status"] in ("good", "fair", "bad"):
            title, situation, advice, kind = texts.describe(item["id"], item["status"], item["message"]["vars"])
            evaluated.append({"id": item["id"], "status": item["status"], "status_name": texts.STATUS_NAME[item["status"]],
                              "title": title, "situation": situation, "advice": advice, "advice_kind": kind,
                              "marker": round(fmt.band_position(item["score"]), 1)})
        else:
            skipped.append({"title": texts.TITLES[item["id"]], "reason": texts.UNAVAILABLE})
    counts = {k: overall[k] for k in ("good", "fair", "bad")}
    status = overall_status(overall["score"])
    first, second = texts.overall_sentences(status, counts)
    loc = result["location"]
    return {
        "kind": "pre", "kicker": "Diagnóstico do perfil no Google", "date_label": "Pré-análise",
        "location": loc, "analysis_id": analysis["id"], "date": _day(analysis["captured_at"]),
        "overall": overall, "status": status, "status_name": texts.STATUS_NAME[status],
        "counts": counts, "sentence_1": first, "sentence_2": second,
        "groups": [{"status": s, "name": texts.STATUS_NAME[s], "help": texts.STATUS_HELP[s],
                    "items": [i for i in evaluated if i["status"] == s]}
                   for s in ("bad", "fair", "good") if any(i["status"] == s for i in evaluated)],
        "competitors": _competitors(result["items"]), "skipped": skipped, "evolution": None,
        "warnings": warnings_for(analysis), "bands": config.OVERALL_BANDS, "summary": summary,
        "filename": f"Pre-Analise-{'Resumo-' if summary else ''}{slug(loc.get('name') or '')}-{_file_day(analysis['captured_at'])}.pdf",
    }
