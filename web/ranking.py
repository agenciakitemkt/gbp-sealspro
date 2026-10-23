"""Analise de Ranking no app local (CLAUDE.md, secao 16).

Telas (mesma protecao das outras: Host local e, nos POST, origem da propria tela):
- GET  /ranking?local=        formulario (cliente, palavra, grade, raio) e analises anteriores do local
- POST /ranking/nova          cria a analise pendente e leva para /ranking/analise
- GET  /ranking/analise?id=   instrucoes, progresso ou resultado (mapa, concorrentes e tabela)
- GET  /ranking/status?id=    andamento em JSON (a tela consulta enquanto a extensao coleta)
- POST /ranking/cancelar?id=  desiste de uma analise pendente

Para o service worker da extensao (origem chrome-extension://<id> + segredo, como /pre/captura; ver web/pre.py):
- POST /ranking/inicio  {place}          clique no botao "Ranking SealsPro" no perfil: devolve a tarefa (pontos)
- POST /ranking/ponto   {id, i, text}    a busca do Maps num ponto
- POST /ranking/fim     {id, cancelled, error}

Todo texto que vem do Maps (nomes, enderecos, categorias) e nao confiavel: autoescape no HTML e, no mapa, so
textContent (os dados vao para o script por |tojson, que escapa <, > e &).
"""

import json
import os
import tempfile
import threading
from contextlib import closing

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

import storage
from report import pdf as report_pdf
from report.build import ReportError
from report.build_ranking import build_ranking_comparison_report, build_ranking_report
from report.render import render_ranking_comparison_html, render_ranking_html
from ranking import config
from ranking import history as rk_history
from ranking.grid import spacing_m
from ranking.service import (RankingError, add_point, begin, client_identity, finish_and_next, new_batch,
                             pending_task, repeat, repeat_batch, set_disabled, shown_status)
from web import pre as pre_web

router = APIRouter()
templates = None  # definido por web.app
EXT_PATHS = ("/ranking/tarefa", "/ranking/inicio", "/ranking/ponto", "/ranking/fim")
_lock = threading.Lock()  # um pedido da extensao por vez (sqlite e a ordem dos pontos)
STATUS_LABELS = {"pendente": "Esperando a extensão", "coletando": "Coletando", "pronta": "Pronta",
                 "erro": "Erro", "cancelada": "Cancelada", "expirada": "Expirada (não foi iniciada)"}


def _active(db, wanted):
    active = storage.list_locations(db, only_active=True)
    current = next((r for r in active if r["id"] == wanted), active[0] if active else None)
    return active, current


@router.get("/ranking", response_class=HTMLResponse)
def ranking_page(request: Request, local: str | None = None, erro: str | None = None):
    with closing(storage.connect()) as db:
        active, current = _active(db, local)
        rankings = storage.list_rankings(db, current["id"]) if current else []
        for r in rankings:
            r["shown"] = shown_status(r)
        reminders = rk_history.due(storage.list_active_rankings(db))
    ident, ident_error = None, None
    if current:
        try:
            ident = client_identity(current["id"])
        except RankingError as e:
            ident_error = str(e)
    evolution = [{**s, "charts": [rk_history.line_chart(s["analyses"], "atrp"), rk_history.line_chart(s["analyses"], "solv")]}
                 for s in rk_history.series(rankings) if len(s["analyses"]) >= 2]
    ctx = {"locais": active, "atual": current, "rankings": rankings, "ident": ident, "ident_erro": ident_error,
           "evolution": evolution, "ready": [r for r in rankings if r["status"] == "pronta"], "reminders": reminders,
           "erro": erro, "cfg": config, "labels": STATUS_LABELS, "picker_url": "/ranking", "picker_target": "#ranking"}
    return templates.TemplateResponse(request, "ranking.html", ctx)


@router.post("/ranking/nova")
async def ranking_nova(request: Request):
    """Formulario da tela (application/x-www-form-urlencoded, lido aqui para nao depender do python-multipart)."""
    body = (await request.body())[:4096].decode("utf-8", "replace")
    form = {k: v[0] for k, v in parse_qs(body).items()}
    local, palavra = form.get("local", ""), form.get("palavra", "")
    try:
        grade, raio = int(form.get("grade", "")), int(form.get("raio", ""))
        zoom = int(form.get("zoom", config.VIEW_DISTANCE_M))
    except ValueError:
        return PlainTextResponse("Grade, raio ou zoom inválido.", status_code=400)
    return await run_in_threadpool(_nova, request, local, palavra, grade, raio, zoom)


def _nova(request, local, palavra, grade, raio, zoom):
    with closing(storage.connect()) as db:
        active, current = _active(db, local)
        if current is None or current["id"] != local:
            return PlainTextResponse("Local não encontrado ou inativo.", status_code=404)
        try:
            ids, batch_id = new_batch(db, current, palavra, grade, raio, zoom)
        except RankingError as e:
            return templates.TemplateResponse(request, "erro.html", {"mensagem": str(e), "local": local},
                                              status_code=400)
    if batch_id:
        return RedirectResponse(f"/ranking/lote?id={batch_id}&iniciar=1", status_code=303)
    return RedirectResponse(f"/ranking/analise?id={ids[0]}&iniciar=1", status_code=303)


@router.get("/ranking/comparar", response_class=HTMLResponse)
def ranking_comparar(request: Request, a: int, b: int):
    """Antes e depois de duas analises prontas da mesma serie (mesma palavra, grade e raio). So le."""
    with closing(storage.connect()) as db:
        ra, rb = storage.get_ranking(db, a), storage.get_ranking(db, b)
        location = None
        error, status, cmp = None, 200, None
        if ra is None or rb is None:
            error, status = "Uma das análises não foi encontrada.", 404
        elif a == b:
            error, status = "Escolha duas análises diferentes.", 400
        else:
            try:
                cmp = rk_history.compare(ra, rb)
            except ValueError as e:
                error, status = str(e), 400
            location = next((l for l in storage.list_locations(db) if l["id"] == ra["location_id"]), None)
    return templates.TemplateResponse(request, "ranking_comparar.html",
                                      {"c": cmp, "erro": error, "local": location, "a_id": a, "b_id": b},
                                      status_code=status)


def _pdf(request, build, render):
    """Monta e gera um PDF do ranking na hora (um PDF por vez no app, a mesma trava dos outros relatorios)."""
    with closing(storage.connect()) as db:
        try:
            report = build(db)
        except ReportError as e:
            return templates.TemplateResponse(request, "erro.html", {"mensagem": str(e), "local": None}, status_code=409)
    if not report_pdf.LOCK.acquire(blocking=False):
        return templates.TemplateResponse(request, "erro.html", {"mensagem": "Já existe um relatório sendo gerado. "
                                                                 "Aguarde terminar.", "local": None}, status_code=409)
    try:
        with tempfile.TemporaryDirectory(prefix="gbp-pdf-") as tmp:
            path = os.path.join(tmp, report["filename"])
            report_pdf.html_to_pdf(render(report), path)
            with open(path, "rb") as f:
                content = f.read()
    except report_pdf.PdfError as e:
        return templates.TemplateResponse(request, "erro.html", {"mensagem": f"Não foi possível gerar o PDF: {e}",
                                                                 "local": None}, status_code=500)
    finally:
        report_pdf.LOCK.release()
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{report["filename"]}"'})


@router.get("/ranking/relatorio.pdf")
def ranking_relatorio_pdf(request: Request, id: int):
    """PDF de uma analise pronta, para o cliente. Gerado na hora (o fundo do mapa vem da internet, ja embutido)."""
    return _pdf(request, lambda db: build_ranking_report(db, id), render_ranking_html)


@router.get("/ranking/comparativo.pdf")
def ranking_comparativo_pdf(request: Request, a: int, b: int):
    """PDF antes e depois de duas analises prontas da mesma serie (a mais antiga e o "antes")."""
    return _pdf(request, lambda db: build_ranking_comparison_report(db, a, b), render_ranking_comparison_html)


def _batch_view(db, batch_id):
    items = storage.list_batch(db, batch_id)
    for r in items:
        r["shown"] = shown_status(r)
        r["received"] = storage.count_ranking_points(db, r["id"]) if r["shown"] == "coletando" else None
    return items


@router.get("/ranking/lote", response_class=HTMLResponse)
def ranking_lote(request: Request, id: int, iniciar: int = 0):
    """Varias palavras-chave de uma vez: andamento de cada uma e, prontas, a comparacao entre elas."""
    with closing(storage.connect()) as db:
        items = _batch_view(db, id)
        if not items:
            return templates.TemplateResponse(request, "erro.html", {"mensagem": "Lote não encontrado.", "local": None},
                                              status_code=404)
        location = next((l for l in storage.list_locations(db) if l["id"] == items[0]["location_id"]), None)
    ready = sorted([r for r in items if r["shown"] == "pronta"], key=lambda r: (-r["result"]["own"]["solv"],
                                                                                 r["result"]["own"]["atrp"]))
    pending = [r for r in items if r["shown"] == "pendente"]
    ext_id = pre_web.extension_settings()[0]
    ctx = {"items": items, "ready": ready, "first": items[0], "local": location, "batch_id": id, "labels": STATUS_LABELS,
           "start": pending[0] if pending and not any(r["shown"] == "coletando" for r in items) else None,
           "running": any(r["shown"] in ("pendente", "coletando") for r in items),
           "ext_id": ext_id if pre_web.EXTENSION_ID.match(ext_id or "") else None, "iniciar": iniciar == 1,
           "cfg": config}
    return templates.TemplateResponse(request, "ranking_lote.html", ctx)


@router.get("/ranking/lote/status")
def ranking_lote_status(id: int):
    with closing(storage.connect()) as db:
        items = _batch_view(db, id)
    return JSONResponse({"items": [{"id": r["id"], "status": r["shown"], "received": r["received"],
                                    "total": (len(r["points"]) - len(r["disabled"])) if r["points"] else r["grid_size"] ** 2 - len(r["disabled"])}
                                   for r in items]})


@router.post("/ranking/lote/repetir")
def ranking_lote_repetir(request: Request, id: int):
    with closing(storage.connect()) as db:
        try:
            ids, batch_id = repeat_batch(db, id)
        except RankingError as e:
            return templates.TemplateResponse(request, "erro.html", {"mensagem": str(e), "local": None}, status_code=400)
    return RedirectResponse(f"/ranking/lote?id={batch_id or ids[0]}&iniciar=1" if batch_id
                            else f"/ranking/analise?id={ids[0]}&iniciar=1", status_code=303)


@router.post("/ranking/pontos")
async def ranking_pontos(request: Request, id: int):
    """Desliga/religa pontos de uma analise pronta (tela do mapa). Corpo JSON {"disabled": [indices]}; a protecao de
    origem das outras telas vale aqui (so a propria tela do app)."""
    try:
        data = json.loads((await request.body())[:20000] or b"{}")
    except ValueError:
        return JSONResponse({"ok": False, "error": "Pedido inválido."}, status_code=400)
    disabled = data.get("disabled") if isinstance(data, dict) else None

    def run():
        with closing(storage.connect()) as db:
            return set_disabled(db, id, disabled)
    try:
        await run_in_threadpool(run)
    except RankingError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    return JSONResponse({"ok": True})


@router.post("/ranking/repetir")
def ranking_repetir(request: Request, id: int):
    """Mesma palavra, grade e raio de uma analise anterior; a tela seguinte ja pede a extensao para comecar."""
    with closing(storage.connect()) as db:
        try:
            new_id = repeat(db, id)
        except RankingError as e:
            return templates.TemplateResponse(request, "erro.html", {"mensagem": str(e), "local": None}, status_code=400)
    return RedirectResponse(f"/ranking/analise?id={new_id}&iniciar=1", status_code=303)


@router.post("/ranking/cancelar")
def ranking_cancelar(id: int):
    with closing(storage.connect()) as db:
        r = storage.get_ranking(db, id)
        if r is None:
            return PlainTextResponse("Análise não encontrada.", status_code=404)
        if r["status"] == "pendente":
            storage.finish_ranking(db, id, "cancelada", error="Cancelada no app.")
    return RedirectResponse(f"/ranking/analise?id={id}", status_code=303)


def _status(db, r):
    status = shown_status(r)
    return {"status": status, "label": STATUS_LABELS.get(status, status),
            "received": storage.count_ranking_points(db, r["id"]),
            "total": (len(r["points"]) or r["grid_size"] ** 2) - len(r["disabled"]),
            "error": r["error"]}


@router.get("/ranking/status")
def ranking_status(id: int):
    with closing(storage.connect()) as db:
        r = storage.get_ranking(db, id)
        if r is None:
            return JSONResponse({"error": "não encontrada"}, status_code=404)
        return JSONResponse(_status(db, r))


@router.get("/ranking/analise", response_class=HTMLResponse)
def ranking_analise(request: Request, id: int, iniciar: int = 0):
    with closing(storage.connect()) as db:
        r = storage.get_ranking(db, id)
        if r is None:
            return templates.TemplateResponse(request, "erro.html", {"mensagem": "Análise de ranking não encontrada.",
                                                                     "local": None}, status_code=404)
        location = next((l for l in storage.list_locations(db) if l["id"] == r["location_id"]), None)
        status = _status(db, r)
    r["shown"] = status["status"]
    maps_url = None
    if r["shown"] == "pendente":
        try:
            maps_url = client_identity(r["location_id"])["mapsUrl"]
        except RankingError:
            maps_url = None
    ext_id = pre_web.extension_settings()[0]
    ctx = {"r": r, "res": r["result"], "st": status, "local": location, "maps_url": maps_url,
           "ext_id": ext_id if pre_web.EXTENSION_ID.match(ext_id or "") else None, "iniciar": iniciar == 1,
           "spacing": spacing_m(r["grid_size"], r["radius_m"]), "labels": STATUS_LABELS}
    return templates.TemplateResponse(request, "ranking_analise.html", ctx)


# ---------------------------------------------------------------------------
# Pedidos do service worker da extensao
# ---------------------------------------------------------------------------

def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


async def _ext_body(request):
    if not pre_web.authorized(request):
        return None, pre_web._denied()
    data, error = await pre_web._read_json(request)
    if error:
        return None, error
    if not isinstance(data, dict):
        return None, PlainTextResponse("Pedido inválido.", status_code=400)
    return data, None


def _run(fn, *args, **kwargs):
    with _lock, closing(storage.connect()) as db:
        return fn(db, *args, **kwargs)


async def _call(fn, *args, **kwargs):
    try:
        return JSONResponse({"ok": True, **(await run_in_threadpool(_run, fn, *args, **kwargs) or {})})
    except RankingError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=409)


@router.post("/ranking/tarefa")
async def ranking_tarefa(request: Request):
    """Clique em "Analisar" no app: a extensao recebeu so o numero da analise e pergunta aqui, com o segredo, qual
    perfil abrir. Assim quem manda a mensagem para a extensao nao escolhe o que sera buscado."""
    data, error = await _ext_body(request)
    if error:
        return error
    rid = _int(data.get("id"))
    if rid is None:
        return PlainTextResponse("Pedido inválido.", status_code=400)
    return await _call(lambda db: pending_task(db, rid))


@router.post("/ranking/inicio")
async def ranking_inicio(request: Request):
    data, error = await _ext_body(request)
    if error:
        return error
    rid = data.get("id")
    if not isinstance(data.get("place"), str) or (rid is not None and _int(rid) is None):
        return PlainTextResponse("Pedido inválido.", status_code=400)
    return await _call(lambda db, place: {"task": begin(db, place, rid)}, data["place"])


@router.post("/ranking/ponto")
async def ranking_ponto(request: Request):
    data, error = await _ext_body(request)
    if error:
        return error
    rid, idx, text = _int(data.get("id")), _int(data.get("i")), data.get("text")
    if rid is None or idx is None or not isinstance(text, str):
        return PlainTextResponse("Pedido inválido.", status_code=400)
    return await _call(add_point, rid, idx, text)


@router.post("/ranking/fim")
async def ranking_fim(request: Request):
    data, error = await _ext_body(request)
    if error:
        return error
    rid = _int(data.get("id"))
    if rid is None:
        return PlainTextResponse("Pedido inválido.", status_code=400)
    err = data.get("error") if isinstance(data.get("error"), str) else None

    def done(db):
        status, nxt = finish_and_next(db, rid, cancelled=data.get("cancelled") is True, error=err)
        return {"status": status, "url": f"/ranking/analise?id={rid}", "next": nxt}
    return await _call(done)
