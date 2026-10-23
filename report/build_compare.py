"""Dados do PDF comparativo (antes e depois) de duas analises da Completa, para entregar ao cliente.

Regras:
- So analises REAIS do mesmo local; a mais antiga e o "antes", qualquer que seja a ordem pedida.
- As duas sao recalculadas com o motor atual a partir dos brutos guardados (em memoria, nada e gravado), para a
  diferenca vir do perfil e nao de uma mudanca de criterio. Sem o bruto, vale a nota guardada so se ela ja for da
  versao atual; senao, nao da para comparar e o relatorio nao e gerado.
- Por item, so o status (Fraco, Razoavel, Bom) antes e depois, a situacao de agora e o que mudou (report.changes);
  nunca a nota do item nem como foi feito. Item que melhorou = subiu de faixa ou, sem cair de faixa, teve alguma
  mudanca para melhor (descricao reescrita, logotipo trocado, fotos novas...). Itens que nao foram avaliados nas
  duas analises ficam de fora.
- Enquanto faltarem fotos de clientes, o PDF traz um bloco em destaque: e a parte do cliente, com o link para
  avaliar e para compartilhar no WhatsApp.
- Nunca texto de avaliacoes de clientes: dos dados do perfil saem so contagens e a nota media.
"""

from urllib.parse import quote

import history
import storage
from collector.normalize import normalize
from report import changes, texts
from report.build import ReportError, _day, _file_day, _item_texts, evolution, is_current_version, real_analysis, slug
from scoring import analyze, config
from scoring.base import overall_status

RANK = {"bad": 0, "fair": 1, "good": 2}

NUMBERS = (  # (rotulo, chave em history.facts, melhor quando 'up' ou 'down', casas decimais)
    ("Avaliações no Google", "reviews", "up", 0),
    ("Nota média", "rating", "up", 1),
    ("Avaliações sem resposta", "unanswered", "down", 0),
    ("Fotos e vídeos da empresa", "owner_media", "up", 0),
    ("Vídeos", "videos", "up", 0),
    ("Fotos e vídeos de clientes", "customer_media", "up", 0),
    ("Postagens", "posts", "up", 0),
)


def _num(value, decimals):
    return "–" if value is None else f"{value:.{decimals}f}".replace(".", ",")


def numbers(profile_before, profile_after):
    """Linhas de numeros do perfil: antes, depois, diferenca e se a mudanca foi boa ('good'), ruim ('bad') ou nula."""
    fa, fb = history.facts(profile_before), history.facts(profile_after)
    rows = []
    for label, key, better, decimals in NUMBERS:
        a, b = fa[key], fb[key]
        delta = None if a is None or b is None else round(b - a, decimals)
        trend = "same" if not delta else ("good" if (delta > 0) == (better == "up") else "bad")
        rows.append({"label": label, "before": _num(a, decimals), "after": _num(b, decimals), "trend": trend,
                     "delta": "–" if delta is None else ("0" if not delta else
                                                         ("+" if delta > 0 else "−") + _num(abs(delta), decimals))})
    return rows


def _side(analysis):
    """(resultado com o motor atual, perfil ou None, bruto ou None)."""
    raw = storage.load_raw_file(analysis["raw_path"])
    if raw is not None:
        profile = normalize(raw)
        return analyze(profile), profile, raw
    if is_current_version(analysis):
        return analysis["result"], None, None
    raise ReportError(f"Os dados guardados da análise de {_day(analysis['analyzed_at'])} não estão mais disponíveis, "
                      "e ela foi feita com critérios de avaliação anteriores. Não dá para comparar as duas com os "
                      "mesmos critérios.")


def _overall(result):
    o = result["overall"]
    if o["score"] is None:
        return None
    status = overall_status(o["score"])
    return {"score": o["score"], "status": status, "status_name": texts.STATUS_NAME[status],
            "counts": {k: o[k] for k in ("good", "fair", "bad")},
            "rotation": -90 + o["score"] * 1.8}


def _items(result_before, result_after, changed=None):
    """Itens por grupo. `changed` = {id: frase do que melhorou} (report.changes), ou None sem os brutos."""
    changed = changed or {}
    before = {i["id"]: i for i in result_before["items"]}
    out = {"improved": [], "worsened": [], "still_low": [], "still_good": []}
    order = [i["id"] for i in result_after["items"]]  # o motor ja entrega do pior para o melhor
    for item_id in order:
        ia, ib = before.get(item_id), next(i for i in result_after["items"] if i["id"] == item_id)
        if ia is None or ia["status"] not in RANK or ib["status"] not in RANK:
            continue  # nao avaliado em uma das duas: fora do comparativo
        title, situation, _, _ = _item_texts(ib)
        row = {"id": item_id, "title": title, "situation": situation,
               "before": ia["status"], "after": ib["status"],
               "before_name": texts.STATUS_NAME[ia["status"]], "after_name": texts.STATUS_NAME[ib["status"]],
               "rose": RANK[ib["status"]] > RANK[ia["status"]], "change": changed.get(item_id)}
        if RANK[ib["status"]] < RANK[ia["status"]]:
            out["worsened"].append(row)
        elif row["rose"] or row["change"]:
            out["improved"].append(row)
        elif ib["status"] == "good":
            out["still_good"].append(row)
        else:
            out["still_low"].append(row)
    out["improved"].sort(key=lambda r: (not r["rose"], RANK[r["before"]]))  # subiu de faixa, de mais baixo, primeiro
    out["worsened"].sort(key=lambda r: RANK[r["after"]])
    return out


def _sentence(before, after, d1, d2, items):
    delta = after["score"] - before["score"]
    if delta > 0:
        first = f"A nota geral subiu de {before['score']} para {after['score']} entre {d1} e {d2}."
    elif delta < 0:
        first = f"A nota geral foi de {before['score']} para {after['score']} entre {d1} e {d2}."
    else:
        first = f"A nota geral se manteve em {after['score']} entre {d1} e {d2}."
    n_up, n_down = len(items["improved"]), len(items["worsened"])
    n_rose = sum(1 for i in items["improved"] if i["rose"])
    parts = []
    if n_up:
        part = f"{n_up} {'item melhorou' if n_up == 1 else 'itens melhoraram'}"
        if n_rose and n_rose < n_up:
            part += f" ({n_rose} {'subiu' if n_rose == 1 else 'subiram'} de faixa)"
        elif n_rose:
            part += " de faixa"
        parts.append(part)
    if n_down:
        parts.append(f"{n_down} {'item precisa' if n_down == 1 else 'itens precisam'} de atenção")
    second = (" e ".join(parts) + ".") if parts else "Nenhum item mudou."
    return first, second[0].upper() + second[1:]


def customer_photos(result, raw):
    """Bloco em destaque das fotos de clientes, enquanto o item nao estiver bom; None quando ja esta."""
    item = next((i for i in result["items"] if i["id"] == "customer_media"), None)
    if item is None or item["status"] not in ("bad", "fair"):
        return None
    v = item["message"]["vars"]
    current, recommended = v.get("current", 0), v.get("recommended", 3)
    name = result["location"]["name"]
    link = changes.review_link(raw) if raw is not None else None
    message = (f"Oi! Você pode deixar uma avaliação para {name} no Google? Se puder, mande junto uma foto: "
               "pode ser do lugar, do produto ou do resultado, não precisa aparecer ninguém. É bem rápido: "
               f"{link}") if link else None
    return {"current": current, "recommended": recommended, "missing": max(recommended - current, 1),
            "link": link, "message": message,
            "whatsapp": f"https://wa.me/?text={quote(message)}" if message else None}


def build_comparison_report(db, a_id, b_id):
    if a_id == b_id:
        raise ReportError("Escolha duas análises diferentes para o comparativo.")
    first = storage.get_analysis(db, a_id)
    if first is None:
        raise ReportError("Análise não encontrada.")
    location_id = first["location_id"]
    a, b = real_analysis(db, location_id, a_id), None
    try:
        b = real_analysis(db, location_id, b_id)
    except ReportError:
        other = storage.get_analysis(db, b_id)
        if other is not None and other["location_id"] != location_id:
            raise ReportError("As duas análises precisam ser do mesmo local.")
        raise
    before, after = sorted((a, b), key=lambda x: (x["analyzed_at"], x["id"]))
    (res_a, prof_a, raw_a), (res_b, prof_b, raw_b) = _side(before), _side(after)
    ov_a, ov_b = _overall(res_a), _overall(res_b)
    if ov_a is None or ov_b is None:
        raise ReportError("Uma das análises não tem nenhum item avaliado. Escolha outra análise.")
    d1, d2 = _day(before["analyzed_at"]), _day(after["analyzed_at"])
    changed = changes.item_changes(raw_a, raw_b) if raw_a is not None and raw_b is not None else None
    items = _items(res_a, res_b, changed)
    s1, s2 = _sentence(ov_a, ov_b, d1, d2, items)
    warnings = []
    for label, res in (("antes", res_a), ("depois", res_b)):
        n = res["overall"]["unavailable"]
        if n:
            warnings.append(f"Na análise de {label}, {n} {'item não pôde' if n == 1 else 'itens não puderam'} ser "
                            f"avaliado(s) e {'fica' if n == 1 else 'ficam'} fora do comparativo.")
    if prof_a is None or prof_b is None:
        warnings.append("Sem os dados guardados de uma das análises: os números do perfil ficam fora do comparativo.")
    loc = res_b["location"]
    evo = evolution(db, location_id, since=before["analyzed_at"], until=after["analyzed_at"])
    return {
        "kind": "comparison", "location": loc, "before": ov_a, "after": ov_b,
        "before_id": before["id"], "after_id": after["id"],
        "date_before": d1, "date_after": d2, "date": f"{d1} a {d2}", "date_label": "Comparativo",
        "delta": ov_b["score"] - ov_a["score"], "sentence_1": s1, "sentence_2": s2,
        "numbers": numbers(prof_a, prof_b) if prof_a is not None and prof_b is not None else None,
        "items": items, "customer_photos": customer_photos(res_b, raw_b),
        "evolution": evo if evo and evo["count"] >= 3 else None,  # com 2 pontos, os dois medidores ja mostram tudo
        "warnings": warnings, "bands": config.OVERALL_BANDS,
        "filename": f"Comparativo-{slug(loc['name'])}-{_file_day(before['analyzed_at'])}"
                    f"-a-{_file_day(after['analyzed_at'])}.pdf",
    }
