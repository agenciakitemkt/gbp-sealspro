"""Agendamento de postagens (tela /postagens, CLAUDE.md secao 17): calendario e lista por local, formulario de
Novidade com pre-visualizacao, envio da imagem e "Publicar agora".

Os POST passam pela protecao de origem de web/app.py. O formulario e lido aqui (application/x-www-form-urlencoded,
sem python-multipart); a imagem chega sozinha, como corpo do pedido, e e conferida e regravada em posts/images.py.
"""

import threading
from contextlib import closing
from datetime import timedelta
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

import storage
from posts import config, form as post_form, images, launchd, view
from posts.google_api import GoogleClient
from posts.publisher import iso, last_run, now_utc, publish_one

router = APIRouter()
templates = None  # definido por web.app
client_factory = GoogleClient  # os testes trocam por um cliente falso
FORM_MAX = 32 * 1024


def start_publish(post_id):
    """Publica em segundo plano (a foto pode levar alguns segundos no Google). Os testes trocam por chamada direta."""
    threading.Thread(target=publish_now, args=(post_id,), daemon=True).start()


def publish_now(post_id):
    with closing(storage.connect()) as db:
        return publish_one(db, post_id, client_factory(), manual=True)


def _active(db, wanted):
    active = storage.list_locations(db, only_active=True)
    current = next((r for r in active if r["id"] == wanted), active[0] if active else None)
    return active, current


def _location(db, location_id):
    return next((r for r in storage.list_locations(db) if r["id"] == location_id), None)


def _publisher_state(now):
    last = last_run()
    return {"installed": launchd.installed(), "last": last,
            "stale": last is None or now - last > timedelta(minutes=config.STALE_PUBLISHER_MINUTES)}


def _error_page(request, message, status, local=None):
    return templates.TemplateResponse(request, "erro.html", {"mensagem": message, "local": local}, status_code=status)


@router.get("/postagens", response_class=HTMLResponse)
def postagens(request: Request, local: str | None = None, mes: str | None = None, vista: str = "calendario",
              ok: str | None = None):
    now = now_utc()
    today = view.today_local(now)
    year, month = view.parse_month(mes, today)
    vista = "lista" if vista == "lista" else "calendario"
    with closing(storage.connect()) as db:
        active, current = _active(db, local)
        ctx = {"locais": active, "atual": current, "picker_url": "/postagens", "picker_target": "#postagens",
               "vista": vista, "ok": ok, "publisher": _publisher_state(now), "status": view.STATUS,
               "display_status": view.display_status, "cta_labels": config.CTA_LABELS}
        if current:
            start, end = view.month_bounds(year, month)
            month_posts = storage.list_posts(db, current["id"], start, end)
            all_posts = storage.list_posts(db, current["id"])
            prev, nxt = view.shift_month(year, month, -1), view.shift_month(year, month, 1)
            ctx.update({
                "weeks": view.calendar_weeks(year, month, month_posts, today), "weekdays": view.WEEKDAYS,
                "month_label": f"{view.MONTHS[month - 1].capitalize()} de {year}", "mes": f"{year:04d}-{month:02d}",
                "prev": f"{prev[0]:04d}-{prev[1]:02d}", "next": f"{nxt[0]:04d}-{nxt[1]:02d}",
                "this_month": f"{today.year:04d}-{today.month:02d}",
                "rows": list(reversed(all_posts)), "alert": view.last_post_alert(db, current["id"], now),
                "login_problem": any(p["error_kind"] == "login" and p["status"] in ("agendada", "falhou")
                                     for p in all_posts),
                "pending": sum(p["status"] in ("atrasada", "falhou", "recusada") for p in all_posts),
            })
    return templates.TemplateResponse(request, "postagens.html", ctx)


def _form_page(request, db, location, post=None, values=None, errors=None, status=200, day=None):
    now = now_utc()
    if values is None:
        if post:
            values = {"texto": post["summary"], "botao": post["cta_type"], "url": post["cta_url"],
                      "imagem": post["image"], "quando": "agendar",
                      "data_hora": view.local(post["scheduled_at"]).strftime("%Y-%m-%dT%H:%M")}
            if view.local(post["scheduled_at"]) < view.local(iso(now)):  # atrasada ou falhou: sugere amanha
                values["data_hora"] = view.default_when(now=now)
        else:
            values = {"texto": "", "botao": "", "url": "", "imagem": "", "quando": "agendar",
                      "data_hora": view.default_when(day if day and day > view.today_local(now) else None, now)}
    when = view.local(post["scheduled_at"]) if post and post["status"] not in view.EDITABLE else None
    if when is None:
        try:
            when = view.local(view.local_to_utc(values.get("data_hora") or ""))
        except ValueError:
            when = view.local(iso(now))
    a_ctx = {"mes": when.strftime("%Y-%m"), "pv_date": when.strftime("%d/%m/%Y")}
    ctx = {"atual": location, "post": post, "v": values, **a_ctx, "erros": errors or [], "cta_labels": config.CTA_LABELS,
           "cta_without_url": sorted(config.CTA_WITHOUT_URL), "max": config.SUMMARY_MAX,
           "status": view.STATUS, "display_status": view.display_status,
           "editable": post is None or post["status"] in view.EDITABLE,
           "deletable": post is not None and post["status"] in view.DELETABLE,
           "late_minutes": _late_minutes(post), "min_side": config.IMAGE_MIN_SIDE}
    return templates.TemplateResponse(request, "postagem.html", ctx, status_code=status)


def _late_minutes(post):
    if not post or not post["published_at"]:
        return 0
    late = (view.parse(post["published_at"]) - view.parse(post["scheduled_at"])).total_seconds() / 60
    return int(late) if late > config.LATE_NOTICE_MINUTES else 0


@router.get("/postagens/nova", response_class=HTMLResponse)
def nova(request: Request, local: str, dia: str | None = None):
    with closing(storage.connect()) as db:
        _, current = _active(db, local)
        if current is None or current["id"] != local:
            return _error_page(request, "Local não encontrado ou inativo.", 404)
        return _form_page(request, db, current, day=view.parse_day(dia))


@router.get("/postagens/editar", response_class=HTMLResponse)
def editar(request: Request, id: int):
    with closing(storage.connect()) as db:
        post = storage.get_post(db, id)
        if post is None:
            return _error_page(request, "Postagem não encontrada.", 404)
        return _form_page(request, db, _location(db, post["location_id"]), post)


async def _read_form(request):
    body = (await request.body())[:FORM_MAX].decode("utf-8", "replace")
    return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}


@router.post("/postagens/salvar")
async def salvar(request: Request):
    return await run_in_threadpool(_salvar, request, await _read_form(request))


def _back(location_id, scheduled_at, ok):
    month = view.local(scheduled_at).strftime("%Y-%m")
    return RedirectResponse(f"/postagens?local={quote(location_id, safe='')}&mes={month}&ok={ok}", status_code=303)


def _salvar(request, form):
    now = now_utc()
    with closing(storage.connect()) as db:
        post = None
        if form.get("id"):
            try:
                post = storage.get_post(db, int(form["id"]))
            except ValueError:
                post = None
            if post is None:
                return _error_page(request, "Postagem não encontrada.", 404)
            location = _location(db, post["location_id"])
            if post["status"] not in view.EDITABLE:
                return _error_page(request, "Esta postagem não pode mais ser alterada.", 409, location["id"])
        else:
            _, location = _active(db, form.get("local"))
            if location is None or location["id"] != form.get("local"):
                return _error_page(request, "Local não encontrado ou inativo.", 404)
        fields, errors = post_form.validate(form, now)
        if errors:
            return _form_page(request, db, location, post, values=form, errors=errors, status=400)
        publish = fields.pop("now")
        if post is None:
            post_id = storage.create_post(db, location["id"], **fields)
        else:
            post_id = post["id"]
            reset = {"status": "agendada", "next_try_at": None, "error": None, "error_kind": None}
            if fields["image"] != post["image"]:
                reset.update(media_name=None, image_url=None)  # outra foto: sobe de novo
            if post["status"] == "falhou":
                reset["attempts"] = 0  # nova chance completa (first_try_at fica: a conferencia de duplicata continua)
            storage.update_post(db, post_id, **fields, **reset)
    if publish:
        start_publish(post_id)
        return RedirectResponse(f"/postagens/editar?id={post_id}", status_code=303)
    return _back(location["id"], fields["scheduled_at"], "agendada")


@router.post("/postagens/publicar")
def publicar(request: Request, id: int):
    """Publicar agora uma agendada, atrasada ou que falhou."""
    with closing(storage.connect()) as db:
        post = storage.get_post(db, id)
        if post is None:
            return _error_page(request, "Postagem não encontrada.", 404)
        if post["status"] not in view.EDITABLE:
            return _error_page(request, "Esta postagem não está esperando publicação.", 409, post["location_id"])
    start_publish(id)
    return RedirectResponse(f"/postagens/editar?id={id}", status_code=303)


@router.post("/postagens/apagar")
def apagar(request: Request, id: int):
    """Tira da fila (so o que ainda nao foi ao ar, ou foi recusado). Nao apaga nada no Google."""
    with closing(storage.connect()) as db:
        post = storage.get_post(db, id)
        if post is None:
            return _error_page(request, "Postagem não encontrada.", 404)
        if post["status"] not in view.DELETABLE:
            return _error_page(request, "Postagem publicada não é apagada por aqui.", 409, post["location_id"])
        storage.delete_post(db, id)
        if post["image"] and post["image"] not in storage.images_in_use(db):
            images.remove(post["image"])
    return _back(post["location_id"], post["scheduled_at"], "apagada")


@router.post("/postagens/imagem")
async def imagem(request: Request):
    """Recebe a imagem como corpo do pedido (a tela manda o arquivo direto). Devolve o token para o formulario."""
    size = request.headers.get("content-length")
    if size and size.isdigit() and int(size) > config.IMAGE_UPLOAD_MAX:
        return JSONResponse({"erro": "Arquivo grande demais (máximo 15 MB)."}, status_code=413)
    data = await request.body()
    try:
        saved = await run_in_threadpool(images.save, data)
    except images.ImageError as e:
        return JSONResponse({"erro": str(e)}, status_code=400)
    return JSONResponse({**saved, "url": f"/postagens/imagem/{saved['token']}"})


@router.get("/postagens/imagem/{token}")
def imagem_ver(token: str):
    if not images.exists(token):
        return PlainTextResponse("Imagem não encontrada.", status_code=404)
    return FileResponse(images.path_for(token), media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})

