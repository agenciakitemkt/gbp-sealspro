"""Pre Analise no app local (CLAUDE.md, secao 13): recebe a captura da extensao e mostra o resultado.

POST /pre/captura e /pre/ping so aceitam pedidos do service worker da nossa extensao:
- Origin exatamente `chrome-extension://<GBP_EXTENSION_ID>` (o Chrome poe essa origem nos pedidos do service worker;
  um pedido de pagina, inclusive do content script, leva a origem do site e e recusado);
- cabecalho X-Seals-Secret igual a GBP_EXTENSION_SECRET (comparacao em tempo constante);
- corpo JSON de ate MAX_BYTES.
Os dois valores ficam no .env (nunca no git). Qualquer falha devolve 403 sem detalhe. Sem cabecalhos CORS: o service
worker, com host_permissions para 127.0.0.1, le a resposta sem precisar deles.

Todo texto capturado (nome, descricao, categorias, avaliacoes) e nao confiavel: a tela usa autoescape e nenhum `|safe`.
"""

import hmac
import json
import re
import threading
from contextlib import closing

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.concurrency import run_in_threadpool

import os
import tempfile

import gbp_auth
import service
import storage
from report import pdf as report_pdf
from report.build import ReportError
from report.build_pre import build_pre_report, is_current_version
from report.render import render_html
from scoring import config as scoring_config

router = APIRouter()
templates = None  # definido por web.app (o mesmo ambiente Jinja, com autoescape e os filtros da tela)

MAX_BYTES = 20 * 1024 * 1024
EXTENSION_ID = re.compile(r"^[a-p]{32}$")   # formato dos IDs de extensao do Chrome
MIN_SECRET = 32
CAPTURE_PATHS = ("/pre/captura", "/pre/ping")
_lock = threading.Lock()  # uma captura por vez


def extension_settings():
    """(id da extensao, segredo) lidos SO do .env da raiz do projeto (gbp_auth.ENV_PATH), a cada pedido: trocar no
    .env vale sem reiniciar o app. O .env da skill (credenciais do Google) nao vale para a extensao."""
    cfg = gbp_auth.project_env()
    return cfg.get("GBP_EXTENSION_ID", ""), cfg.get("GBP_EXTENSION_SECRET", "")


def authorized(request):
    ext_id, secret = extension_settings()
    if not EXTENSION_ID.match(ext_id or "") or len(secret or "") < MIN_SECRET:
        return False  # sem configuracao, nada entra
    origin = request.headers.get("origin", "")
    given = request.headers.get("x-seals-secret", "")
    same_origin = hmac.compare_digest(origin.encode(), f"chrome-extension://{ext_id}".encode())
    same_secret = hmac.compare_digest(given.encode(), secret.encode())
    return same_origin and same_secret


def _denied():
    return PlainTextResponse("Não autorizado.", status_code=403)


async def _read_json(request):
    """Corpo JSON com limite de tamanho; (dados, None) ou (None, resposta de erro)."""
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        return None, PlainTextResponse("Envie JSON.", status_code=415)
    try:
        declared = int(request.headers.get("content-length") or 0)
    except ValueError:
        declared = 0
    if declared > MAX_BYTES:
        return None, PlainTextResponse("Captura grande demais.", status_code=413)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BYTES:
            return None, PlainTextResponse("Captura grande demais.", status_code=413)
    try:
        return json.loads(body), None
    except ValueError:
        return None, PlainTextResponse("JSON inválido.", status_code=400)


@router.post("/pre/ping")
async def pre_ping(request: Request):
    """Para a pagina de opcoes da extensao testar a configuracao (id e segredo)."""
    return Response(status_code=204) if authorized(request) else _denied()


def _store(capture):
    with _lock, closing(storage.connect()) as db:
        return service.store_pre_capture(db, capture)


@router.post("/pre/captura")
async def pre_captura(request: Request):
    if not authorized(request):
        return _denied()
    capture, error = await _read_json(request)
    if error:
        return error
    if not isinstance(capture, dict):
        return PlainTextResponse("Captura inválida.", status_code=400)
    analysis_id, _result = await run_in_threadpool(_store, capture)
    return JSONResponse({"id": analysis_id, "url": f"/pre?id={analysis_id}"})


def safe_url(url):
    """Link capturado so vira href se for http(s); qualquer outra coisa (javascript:, data:...) fica so como texto."""
    return url if isinstance(url, str) and re.match(r"^https?://", url, re.I) else None


@router.get("/pre", response_class=HTMLResponse)
def pre(request: Request, id: int | None = None):
    with closing(storage.connect()) as db:
        if id is None:
            return templates.TemplateResponse(request, "pre_lista.html", {"analises": storage.list_pre_analyses(db)})
        analysis = storage.get_pre_analysis(db, id)
    if analysis is None:
        return templates.TemplateResponse(request, "erro.html", {"mensagem": "Pré análise não encontrada.",
                                                                 "local": None}, status_code=404)
    return templates.TemplateResponse(request, "pre.html", {"a": analysis, "r": analysis["result"],
                                                            "bands": scoring_config.OVERALL_BANDS,
                                                            "versao_antiga": not is_current_version(analysis)})


def _error(request, message, status):
    return templates.TemplateResponse(request, "erro.html", {"mensagem": message, "local": None}, status_code=status)


@router.get("/pre/relatorio.pdf")
def pre_relatorio_pdf(request: Request, id: int, modo: str = "completo"):
    """PDF de uma pre analise guardada, para entregar ao dono do negocio. Gerado na hora, localmente.
    modo=resumo: so a nota e os itens fechados, sem a orientacao de como corrigir."""
    with closing(storage.connect()) as db:
        try:
            report = build_pre_report(db, id, summary=modo == "resumo")
        except ReportError as e:
            return _error(request, str(e), 404 if storage.get_pre_analysis(db, id) is None else 409)
    if not report_pdf.LOCK.acquire(blocking=False):
        return _error(request, "Já existe um relatório sendo gerado. Aguarde terminar.", 409)
    try:
        with tempfile.TemporaryDirectory(prefix="gbp-pdf-") as tmp:
            path = os.path.join(tmp, report["filename"])
            report_pdf.html_to_pdf(render_html(report), path)
            with open(path, "rb") as f:
                content = f.read()
    except report_pdf.PdfError as e:
        return _error(request, f"Não foi possível gerar o PDF: {e}", 500)
    finally:
        report_pdf.LOCK.release()
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{report["filename"]}"'})
