"""Tela de resultado (Fase 3). App local: só escuta em 127.0.0.1 (ver serve.py).

A tela guarda acesso às contas dos clientes, então além de escutar só no loopback ela
recusa Host e Origin que não sejam locais (contra DNS rebinding e requisições de outros sites).
"""

import os
import tempfile
import threading
from contextlib import closing
from urllib.parse import quote, urlparse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

import history
import storage
from scoring import config as scoring_config
from scoring.base import overall_status
import service
from report.build import ReportError, build_report, is_current_version
from report.build_compare import build_comparison_report
from report.pdf import LOCK as _pdf_lock, PdfError, html_to_pdf
from report.render import render_comparison_html, render_html
from service import AnalysisError, run_analysis
from web import format as fmt
from web import postagens as postagens_web
from web import pre as pre_web
from web import leads as leads_web
from web import ranking as ranking_web
from ranking import history as ranking_history
from web import simulador as simulador_web

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_HOSTS = ["127.0.0.1", "localhost"]

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
templates.env.filters.update(msg=fmt.render_message, status_label=fmt.status_label,
                             band_position=fmt.band_position, hours=fmt.format_hours,
                             age=fmt.humanize_age, overall_status=overall_status,
                             local_dt=fmt.local_datetime, local_short=fmt.local_short,
                             local_time=fmt.local_time, local_day=fmt.local_day, br_date=fmt.br_date,
                             kind_label=fmt.kind_label, version_label=history.version_label,
                             safe_url=pre_web.safe_url)
pre_web.templates = templates
ranking_web.templates = templates
leads_web.templates = templates
simulador_web.templates = templates
postagens_web.templates = templates
app.include_router(pre_web.router)
app.include_router(ranking_web.router)
app.include_router(leads_web.router)
app.include_router(simulador_web.router)
app.include_router(postagens_web.router)

sync_job = service.sync_job  # sincronizacao de locais em segundo plano (a tela consulta o estado)
_report_lock = _pdf_lock  # um PDF por vez (cada um abre um Chrome), o mesmo da Pre
_analysis_lock = threading.Lock()  # uma análise por vez: protege a cota da API e evita cliques duplos


@app.middleware("http")
async def same_origin_only(request: Request, call_next):
    """Recusa POST vindo de outro site (CSRF): Origin/Sec-Fetch-Site precisam ser da própria tela."""
    # /pre/captura, /pre/ping e os pedidos de ranking e de leads da extensao tem checagem propria e mais forte (origem
    # da extensao + segredo): web/pre.py, web/ranking.py e web/leads.py
    if request.method not in ("GET", "HEAD", "OPTIONS") \
            and request.url.path not in pre_web.CAPTURE_PATHS + ranking_web.EXT_PATHS + leads_web.EXT_PATHS:
        origin = request.headers.get("origin")
        site = request.headers.get("sec-fetch-site")
        if (origin and urlparse(origin).netloc != request.headers.get("host")) \
                or (site and site not in ("same-origin", "none")):
            return PlainTextResponse("Origem não permitida.", status_code=403)
    return await call_next(request)


def _pick(db, wanted):
    """Local pedido, se for ativo; senão o analisado mais recentemente; senão o primeiro ativo."""
    active = storage.list_locations(db, only_active=True)
    by_id = {r["id"]: r for r in active}
    if wanted in by_id:
        return active, by_id[wanted]
    last = db.execute("SELECT a.location_id FROM analyses a JOIN locations l ON l.id=a.location_id "
                      "WHERE l.active=1 AND a.kind='real' ORDER BY a.analyzed_at DESC LIMIT 1").fetchone()
    if last and last["location_id"] in by_id:
        return active, by_id[last["location_id"]]
    return active, (active[0] if active else None)


def _old_version(analysis):
    """A analise e de uma versao anterior do motor ou do config? O aviso fica so na tela, nunca no PDF."""
    return analysis is not None and not is_current_version(analysis)


def _page(request, db, wanted, error=None, headers=None):
    active, current = _pick(db, wanted)
    analysis = storage.latest_analysis(db, current["id"]) if current else None
    state = sync_job.state()
    ctx = {"locais": active, "atual": current, "analise": analysis, "erro": error,
           "versao_antiga": _old_version(analysis),
           "rankings_vencidos": len(ranking_history.due(storage.list_active_rankings(db))),
           "bands": scoring_config.OVERALL_BANDS,
           # ao abrir a pagina so mostra a sincronizacao se ainda estiver rodando
           "sync": state if state["status"] == "running" else {"status": "idle"}}
    return templates.TemplateResponse(request, "index.html", ctx, headers=headers)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, local: str | None = None):
    with closing(storage.connect()) as db:
        return _page(request, db, local)


@app.post("/analisar", response_class=HTMLResponse)
def analisar(request: Request, local: str):
    with closing(storage.connect()) as db:
        active, current = _pick(db, local)
        if current is None or current["id"] != local:
            return PlainTextResponse("Local não encontrado ou inativo.", status_code=404)
        error = None
        if not _analysis_lock.acquire(blocking=False):
            error = "Já existe uma análise em andamento. Aguarde terminar."
        else:
            try:
                run_analysis(db, current)
            except AnalysisError as e:
                error = f"Não foi possível analisar agora: {e}"
            finally:
                _analysis_lock.release()
        if "hx-request" not in request.headers:
            return RedirectResponse(f"/?local={quote(local, safe='')}", status_code=303)
        # htmx só troca o conteúdo com 200; o erro aparece num aviso dentro da página.
        return _page(request, db, local, error, headers={"HX-Push-Url": f"/?local={quote(local, safe='')}"})


def _sync_fragment(request, headers=None):
    return templates.TemplateResponse(request, "_sync.html", {"sync": sync_job.state()}, headers=headers)


@app.post("/sincronizar", response_class=HTMLResponse)
def sincronizar(request: Request):
    sync_job.start()  # se ja estiver rodando, apenas devolve o andamento atual
    return _sync_fragment(request)


@app.get("/sincronizar/status", response_class=HTMLResponse)
def sincronizar_status(request: Request):
    # Ao terminar com sucesso, avisa a pagina para atualizar o seletor de locais.
    done = sync_job.state()["status"] == "done"
    return _sync_fragment(request, headers={"HX-Trigger": "syncDone"} if done else None)


@app.get("/seletor", response_class=HTMLResponse)
def seletor(request: Request, local: str | None = None):
    with closing(storage.connect()) as db:
        active, current = _pick(db, local)
    return templates.TemplateResponse(request, "_picker.html", {"locais": active, "atual": current})


@app.get("/historico", response_class=HTMLResponse)
def historico(request: Request, local: str | None = None):
    """Linha do tempo das analises guardadas do local (reais e retroativas) e grafico da nota geral."""
    with closing(storage.connect()) as db:
        active, current = _pick(db, local)
        analyses = storage.list_analyses(db, current["id"]) if current else []
    ctx = {"locais": active, "atual": current, "analyses": analyses, "rows": list(reversed(analyses)),
           "chart": history.build_chart(analyses), "bands": scoring_config.OVERALL_BANDS,
           "picker_url": "/historico", "picker_target": "#historico"}
    return templates.TemplateResponse(request, "historico.html", ctx)


@app.get("/comparar", response_class=HTMLResponse)
def comparar(request: Request, a: int, b: int, reavaliar: int = 0):
    """Compara duas analises do mesmo local. So le: a reavaliacao com o motor atual nao grava nada."""
    with closing(storage.connect()) as db:
        error = status = comparison = location = None
        if a == b:
            error, status = "Escolha duas análises diferentes para comparar.", 400
        else:
            try:
                comparison = history.build_comparison(db, a, b, reevaluate=bool(reavaliar))
                location = next(r for r in storage.list_locations(db) if r["id"] == comparison["location_id"])
            except LookupError:
                error, status = "Uma das análises não foi encontrada.", 404
            except ValueError:
                error, status = "As duas análises precisam ser do mesmo local.", 400
    return templates.TemplateResponse(request, "comparar.html",
                                      {"c": comparison, "erro": error, "atual": location, "a_id": a, "b_id": b},
                                      status_code=status or 200)


def _error_page(request, message, status, local=None):
    return templates.TemplateResponse(request, "erro.html", {"mensagem": message, "local": local}, status_code=status)


def _pdf_response(request, render, report, local):
    """Gera o PDF na hora, localmente, e devolve como download. Um PDF por vez."""
    if not _report_lock.acquire(blocking=False):
        return _error_page(request, "Já existe um relatório sendo gerado. Aguarde terminar.", 409, local)
    try:
        with tempfile.TemporaryDirectory(prefix="gbp-pdf-") as tmp:
            path = os.path.join(tmp, report["filename"])
            html_to_pdf(render(report), path)
            with open(path, "rb") as f:
                content = f.read()
    except PdfError as e:
        return _error_page(request, f"Não foi possível gerar o PDF: {e}", 500, local)
    finally:
        _report_lock.release()
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{report["filename"]}"'})


@app.get("/relatorio.pdf")
def relatorio_pdf(request: Request, local: str, modo: str = "completo", analise: int | None = None):
    """PDF da ultima analise REAL do local (ou da analise real `analise` do historico), para entregar ao cliente.
    modo=resumo: so a nota e os itens fechados, sem a orientacao de como corrigir."""
    with closing(storage.connect()) as db:
        _, current = _pick(db, local)
        if current is None or current["id"] != local:
            return _error_page(request, "Local não encontrado ou inativo.", 404)
        try:
            report = build_report(db, local, summary=modo == "resumo", analysis_id=analise)
        except ReportError as e:
            return _error_page(request, str(e), 409, local)
    return _pdf_response(request, render_html, report, local)


@app.get("/comparativo.pdf")
def comparativo_pdf(request: Request, a: int, b: int):
    """PDF antes e depois de duas analises reais do mesmo local, recalculadas com o motor atual (nada e gravado)."""
    with closing(storage.connect()) as db:
        first = storage.get_analysis(db, a)
        local = first["location_id"] if first else None
        try:
            report = build_comparison_report(db, a, b)
        except ReportError as e:
            return _error_page(request, str(e), 409, local)
    return _pdf_response(request, render_comparison_html, report, local)
