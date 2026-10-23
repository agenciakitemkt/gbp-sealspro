"""Busca de Leads no app local (CLAUDE.md, secao 18).

Telas (mesma protecao das outras: Host local e, nos POST, origem da propria tela):
- GET  /leads                   formulario (palavra-chave, regiao, abrangencia) e buscas anteriores
- POST /leads/nova              localiza a regiao, cria a busca pendente e leva para /leads/busca (a extensao comeca)
- GET  /leads/busca?id=         andamento ou resultado (filtros, ordem, cartoes, tabela e mapa)
- GET  /leads/favoritos         os leads marcados com estrela, de todas as buscas
- GET  /leads/status?id=        andamento em JSON
- POST /leads/cancelar?id=, /leads/repetir?id=, /leads/apagar?id=
- POST /leads/nota              JSON {key, note}: nota da SealsPro sobre o negocio (vale em todas as buscas)
- POST /leads/favorito          JSON {key, search, on}
- POST /leads/planilha.csv      JSON {search | "favoritos", keys | null}: planilha dos leads (todos ou os filtrados)

Para o service worker da extensao (origem chrome-extension://<id> + segredo, como /ranking/*; ver web/pre.py):
- POST /leads/tarefa  {id}             o que buscar (pedidos: ponto e pagina)
- POST /leads/ponto   {id, i, text}    uma pagina da busca do Maps; a resposta diz quantos pedidos pular
- POST /leads/fim     {id, cancelled, error}

Todo texto que vem do Maps e nao confiavel: autoescape no HTML; os leads vao para o script por |tojson (que escapa
<, > e &) e a tela monta tudo com textContent; link so vira href se for http(s).
"""

import json
import threading
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

import storage
from leads import config
from leads.service import LeadsError, add_page, finish, new_search, repeat, shown_status, task, to_csv
from web import pre as pre_web

router = APIRouter()
templates = None  # definido por web.app
EXT_PATHS = ("/leads/tarefa", "/leads/ponto", "/leads/fim")
_lock = threading.Lock()  # um pedido da extensao por vez (sqlite e a ordem das paginas)
NOTE_MAX = 2000
STATUS_LABELS = {"pendente": "Esperando a extensão", "coletando": "Coletando", "pronta": "Pronta",
                 "erro": "Erro", "cancelada": "Cancelada", "expirada": "Expirada (não foi iniciada)"}


def _ext_id():
    ext_id = pre_web.extension_settings()[0]
    return ext_id if pre_web.EXTENSION_ID.match(ext_id or "") else None


def _minutes(scope):
    s = config.SCOPES[scope]
    return max(1, round(s["grid"] ** 2 * s["pages"] * config.SECONDS_PER_REQUEST / 60))


@router.get("/leads", response_class=HTMLResponse)
def leads_page(request: Request, erro: str | None = None, palavra: str = "", regiao: str = "",
               abrangencia: str = config.DEFAULT_SCOPE):
    with closing(storage.connect()) as db:
        searches = storage.list_lead_searches(db)
        favorites = len(storage.lead_favorites(db))
    for s in searches:
        s["shown"] = shown_status(s)
    scopes = [{"id": k, **v, "minutes": _minutes(k)} for k, v in config.SCOPES.items()]
    ctx = {"searches": searches, "favorites": favorites, "erro": erro, "scopes": scopes, "cfg": config,
           "labels": STATUS_LABELS, "palavra": palavra, "regiao": regiao,
           "abrangencia": abrangencia if abrangencia in config.SCOPES else config.DEFAULT_SCOPE}
    return templates.TemplateResponse(request, "leads.html", ctx)


@router.post("/leads/nova")
async def leads_nova(request: Request):
    """Formulario da tela (application/x-www-form-urlencoded, lido aqui para nao depender do python-multipart)."""
    body = (await request.body())[:4096].decode("utf-8", "replace")
    form = {k: v[0] for k, v in parse_qs(body).items()}
    return await run_in_threadpool(_nova, request, form.get("palavra", ""), form.get("regiao", ""),
                                   form.get("abrangencia", config.DEFAULT_SCOPE))


def _nova(request, palavra, regiao, abrangencia):
    with closing(storage.connect()) as db:
        try:
            sid = new_search(db, palavra, regiao, abrangencia)
        except LeadsError as e:
            return leads_page(request, erro=str(e), palavra=palavra, regiao=regiao, abrangencia=abrangencia)
    return RedirectResponse(f"/leads/busca?id={sid}&iniciar=1", status_code=303)


def _status(db, s):
    status = shown_status(s)
    return {"status": status, "label": STATUS_LABELS.get(status, status),
            "received": storage.count_lead_pages(db, s["id"]), "total": len(s["requests"]), "error": s["error"]}


@router.get("/leads/status")
def leads_status(id: int):
    with closing(storage.connect()) as db:
        s = storage.get_lead_search(db, id)
        if s is None:
            return JSONResponse({"error": "não encontrada"}, status_code=404)
        return JSONResponse(_status(db, s))


def _pre_by_cid(db, cids):
    """Ultima pre analise de cada CID (para o lead mostrar a nota e o link)."""
    if not cids:
        return {}
    out = {}
    for row in db.execute("SELECT id, cid, score FROM pre_analyses ORDER BY analyzed_at, id"):
        if row["cid"] in cids:
            out[row["cid"]] = {"id": row["id"], "score": row["score"]}
    return out


def _results_ctx(db, leads, search_id):
    notes = storage.lead_notes(db)
    favorites = set(storage.lead_favorites(db))
    pre = _pre_by_cid(db, {l.get("cid") for l in leads if l.get("cid")})
    return {"leads": leads, "notes": {l["key"]: notes[l["key"]] for l in leads if l["key"] in notes},
            "favorites": [l["key"] for l in leads if l["key"] in favorites], "pre": pre, "search": search_id}


@router.get("/leads/busca", response_class=HTMLResponse)
def leads_busca(request: Request, id: int, iniciar: int = 0):
    with closing(storage.connect()) as db:
        s = storage.get_lead_search(db, id)
        if s is None:
            return templates.TemplateResponse(request, "erro.html", {"mensagem": "Busca de leads não encontrada.",
                                                                     "local": None}, status_code=404)
        st = _status(db, s)
        data = _results_ctx(db, s["result"]["leads"], id) if s["result"] else None
    s["shown"] = st["status"]
    if data is not None:
        data["region"] = s["region"]
    ctx = {"s": s, "res": s["result"], "st": st, "data": data, "scope": config.SCOPES.get(s["scope"], {}),
           "ext_id": _ext_id(), "iniciar": iniciar == 1, "labels": STATUS_LABELS, "favoritos": False,
           "minutes": _minutes(s["scope"]) if s["scope"] in config.SCOPES else None}
    return templates.TemplateResponse(request, "leads_busca.html", ctx)


@router.get("/leads/favoritos", response_class=HTMLResponse)
def leads_favoritos(request: Request):
    with closing(storage.connect()) as db:
        leads = list(storage.lead_favorites(db).values())
        data = _results_ctx(db, leads, "favoritos")
    data["region"] = None
    ctx = {"s": None, "res": {"total": len(leads)}, "st": None, "data": data, "scope": {}, "ext_id": None,
           "iniciar": False, "labels": STATUS_LABELS, "favoritos": True, "minutes": None}
    return templates.TemplateResponse(request, "leads_busca.html", ctx)


@router.post("/leads/cancelar")
def leads_cancelar(id: int):
    with closing(storage.connect()) as db:
        s = storage.get_lead_search(db, id)
        if s is None:
            return PlainTextResponse("Busca não encontrada.", status_code=404)
        if s["status"] == "pendente":
            storage.finish_lead_search(db, id, "cancelada", error="Cancelada no app.")
    return RedirectResponse(f"/leads/busca?id={id}", status_code=303)


@router.post("/leads/repetir")
def leads_repetir(request: Request, id: int):
    with closing(storage.connect()) as db:
        try:
            sid = repeat(db, id)
        except LeadsError as e:
            return leads_page(request, erro=str(e))
    return RedirectResponse(f"/leads/busca?id={sid}&iniciar=1", status_code=303)


@router.post("/leads/apagar")
def leads_apagar(id: int):
    with closing(storage.connect()) as db:
        s = storage.get_lead_search(db, id)
        if s is None:
            return PlainTextResponse("Busca não encontrada.", status_code=404)
        if s["status"] == "coletando":
            return PlainTextResponse("A busca ainda está coletando. Cancele no Maps antes de apagar.",
                                     status_code=409)
        storage.delete_lead_search(db, id)
    return RedirectResponse("/leads", status_code=303)


async def _page_json(request):
    """JSON pequeno vindo da propria tela (a origem ja foi conferida em web/app.py)."""
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        return None
    body = await request.body()
    if len(body) > 512 * 1024:
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _key(v):
    return v if isinstance(v, str) and 0 < len(v) <= 100 else None


@router.post("/leads/nota")
async def leads_nota(request: Request):
    data = await _page_json(request)
    key = _key((data or {}).get("key"))
    note = (data or {}).get("note")
    if key is None or not isinstance(note, str) or len(note) > NOTE_MAX:
        return PlainTextResponse("Pedido inválido.", status_code=400)
    with closing(storage.connect()) as db:
        storage.save_lead_note(db, key, note.strip())
    return JSONResponse({"ok": True})


def _find_lead(db, search, key):
    if search == "favoritos":
        return storage.lead_favorites(db).get(key), None
    if not isinstance(search, int) or isinstance(search, bool):
        return None, None
    s = storage.get_lead_search(db, search)
    if s is None or not s["result"]:
        return None, None
    return next((l for l in s["result"]["leads"] if l["key"] == key), None), search


@router.post("/leads/favorito")
async def leads_favorito(request: Request):
    data = await _page_json(request)
    key = _key((data or {}).get("key"))
    on = (data or {}).get("on")
    if key is None or not isinstance(on, bool):
        return PlainTextResponse("Pedido inválido.", status_code=400)
    with closing(storage.connect()) as db:
        if on:
            lead, sid = _find_lead(db, data.get("search"), key)
            if lead is None:
                return PlainTextResponse("Lead não encontrado.", status_code=404)
            lead = {k: v for k, v in lead.items() if k != "searchId"}
            storage.set_lead_favorite(db, key, lead, sid, True)
        else:
            storage.set_lead_favorite(db, key, None, None, False)
    return JSONResponse({"ok": True})


@router.post("/leads/planilha.csv")
async def leads_planilha(request: Request):
    data = await _page_json(request)
    if data is None:
        return PlainTextResponse("Pedido inválido.", status_code=400)
    search, keys = data.get("search"), data.get("keys")
    if keys is not None and not (isinstance(keys, list) and all(_key(k) for k in keys)):
        return PlainTextResponse("Pedido inválido.", status_code=400)
    with closing(storage.connect()) as db:
        if search == "favoritos":
            leads, name = list(storage.lead_favorites(db).values()), "Leads-favoritos"
        elif isinstance(search, int) and not isinstance(search, bool):
            s = storage.get_lead_search(db, search)
            if s is None or not s["result"]:
                return PlainTextResponse("Busca não encontrada.", status_code=404)
            leads, name = s["result"]["leads"], f"Leads-{search}"
        else:
            return PlainTextResponse("Pedido inválido.", status_code=400)
        notes = storage.lead_notes(db)
    if keys is not None:
        wanted = set(keys)
        order = {k: n for n, k in enumerate(keys)}
        leads = sorted((l for l in leads if l["key"] in wanted), key=lambda l: order[l["key"]])
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(to_csv(leads, notes), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}-{stamp}.csv"'})


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
    except LeadsError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=409)


@router.post("/leads/tarefa")
async def leads_tarefa(request: Request):
    """Clique em "Buscar" no app: a extensao recebeu so o numero da busca e pergunta aqui, com o segredo, o que
    buscar. Assim quem manda a mensagem para a extensao nao escolhe o que sera buscado."""
    data, error = await _ext_body(request)
    if error:
        return error
    sid = _int(data.get("id"))
    if sid is None:
        return PlainTextResponse("Pedido inválido.", status_code=400)
    return await _call(lambda db: {"task": task(db, sid)})


@router.post("/leads/ponto")
async def leads_ponto(request: Request):
    data, error = await _ext_body(request)
    if error:
        return error
    sid, idx, text = _int(data.get("id")), _int(data.get("i")), data.get("text")
    if sid is None or idx is None or not isinstance(text, str):
        return PlainTextResponse("Pedido inválido.", status_code=400)
    return await _call(add_page, sid, idx, text)


@router.post("/leads/fim")
async def leads_fim(request: Request):
    data, error = await _ext_body(request)
    if error:
        return error
    sid = _int(data.get("id"))
    if sid is None:
        return PlainTextResponse("Pedido inválido.", status_code=400)
    err = data.get("error") if isinstance(data.get("error"), str) else None
    return await _call(lambda db: {"status": finish(db, sid, cancelled=data.get("cancelled") is True, error=err),
                                   "url": f"/leads/busca?id={sid}"})
