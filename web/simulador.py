"""Simulador de avaliacoes (tela /simulador): parte da ultima analise real da Completa (?local=) ou de uma pre analise
(?pre=). So le o banco; as contas ficam em simulator.py. Os campos do formulario sao recalculados no servidor (htmx)."""

from contextlib import closing

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

import simulator
import storage

router = APIRouter()
templates = None  # definido por web.app


def _source(db, local, pre):
    """(nome, localizacao do resultado, link de volta) ou None."""
    if pre is not None:
        analysis = storage.get_pre_analysis(db, pre)
        if analysis:
            return analysis["result"]["location"], f"/pre?id={pre}"
    elif local:
        analysis = storage.latest_analysis(db, local)  # so analises reais
        if analysis:
            return analysis["result"]["location"], f"/?local={local}"
    return None


@router.get("/simulador", response_class=HTMLResponse)
def simulador(request: Request, local: str | None = None, pre: int | None = None, meta: int | None = None,
              ritmo: int = 5, periodo: str = "semana"):
    with closing(storage.connect()) as db:
        found = _source(db, local, pre)
    if found is None:
        return templates.TemplateResponse(request, "erro.html", {"mensagem": "Análise não encontrada.", "local": None},
                                          status_code=404)
    loc, back = found
    error = sim = None
    try:
        sim = simulator.simulate(loc.get("starDistribution"), loc.get("rating"), loc.get("reviewCount"),
                                 target=meta, pace=ritmo, period=periodo)
    except simulator.SimulatorError as e:
        error = str(e)
    ctx = {"loc": loc, "s": sim, "erro": error, "voltar": back, "local": local, "pre": pre,
           "periodos": simulator.PERIOD_NAMES}
    return templates.TemplateResponse(request, "simulador.html", ctx)
