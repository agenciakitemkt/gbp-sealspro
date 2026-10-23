"""HTML do relatorio (Jinja). Fontes e logos vem de assets/, por caminho de arquivo local: nada e baixado."""

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"

_env = Environment(loader=FileSystemLoader(str(HERE / "templates")), autoescape=select_autoescape(["html"]))
FILLER = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore"


def mask(text):
    """Texto neutro do mesmo tamanho, para o titulo borrado do PDF resumido: o titulo real nao entra no arquivo
    (o borrado do Chrome pode deixar o texto selecionavel)."""
    n = max(4, len(text or ""))
    return (FILLER * (n // len(FILLER) + 1))[:n].strip()


_env.filters["mask"] = mask


def asset_urls():
    uri = lambda *p: (ASSETS.joinpath(*p)).as_uri()  # noqa: E731
    return {
        "inter_regular": uri("fonts", "Inter-Regular.ttf"), "inter_semibold": uri("fonts", "Inter-SemiBold.ttf"),
        "inter_bold": uri("fonts", "Inter-Bold.ttf"),
        "grotesk_medium": uri("fonts", "SpaceGrotesk-Medium.ttf"), "grotesk_bold": uri("fonts", "SpaceGrotesk-Bold.ttf"),
        "logo": uri("logo-sealspro-horizontal.png"), "symbol": uri("logo-sealspro-simbolo.png"),
    }


def render_html(report):
    gauge = {"rotation": -90 + report["overall"]["score"] * 1.8,
             "fair_from": report["bands"]["fair_from"], "good_from": report["bands"]["good_from"]}
    return _env.get_template("relatorio.html").render(r=report, a=asset_urls(), gauge=gauge)


def render_comparison_html(report):
    """HTML do PDF comparativo (report.build_compare)."""
    return _env.get_template("comparativo.html").render(r=report, a=asset_urls())


def render_ranking_html(report):
    """HTML do PDF da Analise de Ranking (report.build_ranking)."""
    return _env.get_template("ranking.html").render(r=report, a=asset_urls())


def render_ranking_comparison_html(report):
    """HTML do PDF comparativo da Analise de Ranking (report.build_ranking)."""
    return _env.get_template("ranking_comparativo.html").render(r=report, a=asset_urls())
