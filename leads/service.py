"""Fluxo da Busca de Leads no app (CLAUDE.md, secao 18):
1. new_search: o usuario escolhe palavra-chave, regiao e abrangencia; o app localiza a regiao (OpenStreetMap), monta a
   grade e a lista de pedidos; a busca fica "pendente".
2. task: o clique na tela manda so o numero da busca para a extensao, que pergunta aqui, com o segredo, o que buscar
   ("coletando").
3. add_page: a extensao manda cada pagina da busca do Maps; o app le e guarda (bruto compactado em data/raw/leads/).
   Pagina com menos de 20 resultados: as seguintes do mesmo ponto sao puladas (a resposta diz quantas).
4. finish: junta os leads sem repetir, calcula a qualidade de cada um e grava ("pronta").
"""

import csv
import io
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import storage
from leads import config, plan, reader
from leads.quality import quality
from leads.region import find_region


class LeadsError(Exception):
    """Mensagem em portugues, para mostrar na tela ou na faixa da extensao."""


def _clean(text, limit, label):
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t:
        raise LeadsError(f"Informe {label}.")
    if len(t) > limit:
        raise LeadsError(f"{label[0].upper()}{label[1:]} longa demais (máximo {limit} caracteres).")
    return t


def locate(text):
    """Indirecao para os testes trocarem o geocodificador (sem internet)."""
    return find_region(text)


def new_search(db, keyword, region_text, scope=config.DEFAULT_SCOPE):
    keyword = _clean(keyword, config.KEYWORD_MAX, "a palavra-chave")
    region_text = _clean(region_text, config.REGION_MAX, "a região")
    if scope not in config.SCOPES:
        raise LeadsError("Abrangência inválida.")
    region = locate(region_text)
    if region is None:
        raise LeadsError("Não foi possível localizar a região no mapa. Escreva como “Bairro, Cidade - UF” ou "
                         "“Cidade - UF”, e confira a internet.")
    s = config.SCOPES[scope]
    try:
        points, view = plan.make_points(region, s["grid"])
    except plan.RegionError as e:
        raise LeadsError(str(e)) from None
    requests = plan.requests_for(points, s["pages"])
    return storage.create_lead_search(db, keyword, region_text, region, scope, s["grid"], s["pages"], view, requests,
                                      config.LEADS_VERSION)


def repeat(db, search_id):
    old = storage.get_lead_search(db, search_id)
    if old is None:
        raise LeadsError("Busca não encontrada.")
    return new_search(db, old["keyword"], old["region_text"], old["scope"])


def _pending_since():
    return (datetime.now(timezone.utc) - timedelta(minutes=config.PENDING_TTL_MIN)).isoformat(timespec="seconds")


def shown_status(search):
    """Busca pendente que passou do prazo aparece como "expirada" (nao e mais aceita)."""
    if search["status"] == "pendente" and search["created_at"] < _pending_since():
        return "expirada"
    return search["status"]


def search_url(keyword, lat, lng):
    """Busca da palavra no Maps, no centro da regiao: a pagina traz o modelo do pedido tbm=map (preload) que a
    extensao usa em cada pedido, trocando so as coordenadas, a distancia de visao e a pagina."""
    return (f"https://www.google.com/maps/search/{quote(keyword, safe='').replace('%20', '+')}/"
            f"@{lat:.7f},{lng:.7f},13z?hl=pt-BR")


def task(db, search_id):
    """Clique em "Buscar" no app: a extensao recebeu so o numero e pergunta aqui o que buscar. A busca passa a
    "coletando". Nada alem disto sai do app."""
    s = storage.get_lead_search(db, search_id)
    if s is None or s["status"] != "pendente" or s["created_at"] < _pending_since():
        raise LeadsError("esta busca não está mais esperando. Prepare outra no app.")
    storage.start_lead_search(db, search_id)
    return {"id": s["id"], "mode": "leads", "keyword": s["keyword"], "view": s["view_m"], "points": s["requests"],
            "searchUrl": search_url(s["keyword"], s["region"]["lat"], s["region"]["lng"])}


def _collecting(db, search_id):
    s = storage.get_lead_search(db, search_id)
    if s is None or s["status"] != "coletando":
        raise LeadsError("busca de leads não está em coleta.")
    return s


def add_page(db, search_id, idx, text):
    """Um pedido (ponto e pagina). Resposta ilegivel fica guardada como None (avisada no fim). Devolve o andamento e
    quantos pedidos seguintes a extensao deve pular (as outras paginas do mesmo ponto, quando esta veio incompleta)."""
    s = _collecting(db, search_id)
    n = len(s["requests"])
    if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx < n:
        raise LeadsError("pedido fora da lista.")
    storage.save_lead_raw(search_id, idx, text)
    read = reader.read_page(text)
    leads, organic = read if read is not None else (None, 0)
    storage.save_lead_page(db, search_id, idx, organic, leads)
    skip = 0
    if read is not None and organic < config.RESULTS_PER_PAGE:
        page = idx % s["pages"]
        skip = s["pages"] - 1 - page
        for k in range(idx + 1, idx + 1 + skip):
            storage.save_lead_page(db, search_id, k, -1, [])
    return {"received": storage.count_lead_pages(db, search_id), "total": n, "skip": skip}


def build_result(search, pages):
    """Junta os leads de todas as paginas, sem repetir (pela ordem dos pedidos: o primeiro que aparece fica), com a
    qualidade, se fica dentro da regiao e quantas vezes apareceu."""
    by_key, order = {}, []
    unread = [i for i in range(len(search["requests"])) if i not in pages or pages[i]["results"] is None]
    for i in sorted(pages):
        for lead in pages[i]["results"] or []:
            k = lead["key"]
            if k in by_key:
                by_key[k]["hits"] += 1
                continue
            by_key[k] = {**lead, "hits": 1, "order": len(order) + 1}
            order.append(k)
    leads = []
    for k in order:
        lead = by_key[k]
        lead["quality"] = quality(lead)
        lead["inside"] = plan.inside(search["region"], lead.get("lat"), lead.get("lng"))
        lead["sab"] = not lead.get("address")
        leads.append(lead)
    return {"leads": leads, "total": len(leads), "unread": unread,
            "skipped": sum(1 for p in pages.values() if p["organic"] == -1)}


def finish(db, search_id, cancelled=False, error=None):
    """Fim da coleta. Cancelada ou com erro: guarda o motivo; os leads ja lidos tambem ficam, para nao perder a
    busca inteira por causa de um captcha no fim. Devolve a situacao final."""
    s = storage.get_lead_search(db, search_id)
    if s is not None and s["status"] == "pendente" and (cancelled or error):
        storage.finish_lead_search(db, search_id, "cancelada" if cancelled else "erro",
                                   error="Cancelada no Maps." if cancelled else str(error)[:300])
        return "cancelada" if cancelled else "erro"
    s = _collecting(db, search_id)
    pages = storage.lead_pages(db, search_id)
    result = build_result(s, pages)
    if cancelled or error:
        status = "cancelada" if cancelled else "erro"
        storage.finish_lead_search(db, search_id, status, result=result if result["total"] else None,
                                   error="Cancelada no Maps." if cancelled else str(error)[:300])
        return status
    if len(result["unread"]) == len(s["requests"]):
        storage.finish_lead_search(db, search_id, "erro", error="Nenhuma página pôde ser lida (o formato da busca "
                                                                "do Maps pode ter mudado).")
        return "erro"
    if result["unread"]:
        result["warning"] = f"{len(result['unread'])} página(s) não chegaram ou não puderam ser lidas."
    storage.finish_lead_search(db, search_id, "pronta", result=result)
    return "pronta"


# ---------------------------------------------------------------------------
# Planilha
# ---------------------------------------------------------------------------

CSV_HEADERS = ("Nome", "Categorias", "Endereço", "Telefone", "Site", "Nota", "Avaliações", "Verificado",
               "Horário", "Qualidade estimada", "Dentro da região", "Google Maps", "Nota da SealsPro")


def _cell(value):
    """Texto vindo do Google numa planilha: um valor que comeca com = + - @ viraria formula no Excel/Sheets."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def maps_link(lead):
    if lead.get("cid"):
        return f"https://www.google.com/maps?cid={lead['cid']}"
    if lead.get("placeId"):
        return f"https://www.google.com/maps/search/?api=1&query=Google&query_place_id={quote(lead['placeId'])}"
    return ""


def to_csv(leads, notes):
    """Leads -> texto CSV (UTF-8 com BOM, separado por ponto e virgula, como o Excel em portugues abre)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(CSV_HEADERS)
    for lead in leads:
        hours = "; ".join(f"{d}: {', '.join(h) or 'Fechado'}" for d, h in (lead.get("hours") or {}).items())
        rating = lead.get("rating")
        w.writerow([_cell(v) for v in (
            lead.get("name"), ", ".join(lead.get("categories") or []),
            "Sem endereço (atende por área)" if lead.get("sab") else lead.get("address"),
            lead.get("phone"), lead.get("website"),
            "" if rating is None else str(rating).replace(".", ","),
            "" if lead.get("reviews") is None else lead["reviews"],
            "Sim" if lead.get("verified") else "Não", hours,
            (lead.get("quality") or {}).get("score"),
            {True: "Sim", False: "Não"}.get(lead.get("inside"), ""),
            maps_link(lead), notes.get(lead.get("key"), ""))])
    return "﻿" + buf.getvalue()
