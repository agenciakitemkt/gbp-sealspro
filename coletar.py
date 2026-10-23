#!/usr/bin/env python3
"""Fase 1: coletor. Gera o perfil normalizado (secao 7) e guarda o JSON bruto de cada coleta.

  python3 coletar.py sincronizar            # atualiza a lista de locais (novos entram ativos)
  python3 coletar.py locais                 # lista locais com ativo/inativo
  python3 coletar.py ativar <alvo>          # tambem: desativar
  python3 coletar.py coletar <alvo>         # coleta um local (mesmo inativo) e guarda o bruto
  python3 coletar.py coletar --todos        # coleta todos os locais ativos
  python3 coletar.py perfil <alvo>          # imprime o perfil normalizado da ultima coleta
  python3 coletar.py retroativas            # cria analises retroativas (motor atual) a partir dos brutos em data/raw
  python3 coletar.py relatorio <alvo> [--analise ID] [--saida PASTA] [--resumo]
                                            # PDF da ultima analise real (ou da analise ID do historico), para o cliente (data/relatorios)
  python3 coletar.py diagnostico <alvo> [--analisar]  # JSON com o que falta em cada item (contrato para ferramentas externas)
  python3 coletar.py comparativo <ID_A> <ID_B> [--saida PASTA]  # PDF antes e depois de duas analises reais (ids no /historico)
  python3 coletar.py relatorio-pre <id> [--saida PASTA] [--resumo]  # PDF de uma pre analise (id da tela /pre); --resumo: so a nota
  python3 coletar.py calibrar [--map "nome no arquivo"=<alvo>] [--top 5] [--so-divergencias] [--incluir-historico]
                                            # compara o motor com data/reference/*.json (GBP Check)
  python3 coletar.py calibrar-pre [--arquivo CAMINHO] [--so-divergencias]
                                            # Pre Analise: roda o motor nos casos de pre_analises_original.json e compara item a item
  python3 coletar.py segredo-extensao [--novo]  # gera o segredo da extensao no .env e mostra uma vez para colar nas opcoes
  python3 coletar.py id-extensao <ID>       # grava no .env o ID da extensao (chrome://extensions)
  python3 coletar.py publicar               # uma passada do publicador de postagens (o agendador do macOS chama este)
  python3 coletar.py publicador instalar    # liga o agendador do macOS (a cada 5 min e ao acordar); tambem: remover, status
"""

import argparse
import json
import os
import re
import secrets
import sys

import gbp_auth

import diagnostico

import storage
from calibration import calibrate
from calibration_pre import calibrate_pre
from report.build import ReportError, build_report
from report.build_compare import build_comparison_report
from report.build_pre import build_pre_report
from report.pdf import PdfError, html_to_pdf
from report.render import render_comparison_html, render_html
from service import AnalysisError, SyncError, run_analysis, backfill_retroactive, store_analysis, sync_locations
from collector.google import fetch_raw
from collector.normalize import normalize


def cmd_sincronizar(db, _):
    try:
        result = sync_locations(db, lambda p: print(
            f"  conta {p['accounts_done']}/{p['accounts_total']}: {p['locations_found']} locais encontrados"))
    except SyncError as e:
        sys.exit(f"Falha ao sincronizar: {e}")
    print(f"{result.total} locais ({result.new} novos).")
    cmd_locais(db, None)


def cmd_locais(db, _):
    for r in storage.list_locations(db):
        marca = "ativo  " if r["active"] else "inativo"
        print(f"{marca}  {r['id']}  {r['title']}  [{r['city'] or '-'}]  coleta: {r['last_collected_at'] or 'nunca'}")


def cmd_ativar(db, args, ativo=True):
    r = storage.find_location(db, args.alvo)
    storage.set_active(db, r["id"], ativo)
    db.commit()
    print(f"{r['title']}: {'ativo' if ativo else 'inativo'}")


def coletar_um(db, r):
    raw = fetch_raw(r["account_id"], r["id"])
    path = storage.save_raw(db, r["id"], raw)
    store_analysis(db, r["id"], raw, path)  # tambem guarda a analise (real): alimenta o historico
    p = normalize(raw)
    loc = p["location"]
    aviso = f"  ATENCAO falhou: {', '.join(raw['errors'])}" if raw["errors"] else ""
    print(f"OK {loc['name']}: {loc['reviewCount']} avaliacoes (nota {loc['rating']}), "
          f"{len(p['media'])} midias, {len(p['customerMedia'])} de clientes, {len(p['posts'])} posts{aviso}")
    print(f"   bruto: {path}")


def cmd_coletar(db, args):
    if args.todos:
        alvos = storage.list_locations(db, only_active=True)
    elif args.alvo:
        alvos = [storage.find_location(db, args.alvo)]
    else:
        sys.exit("Informe um local ou --todos.")
    for r in alvos:
        coletar_um(db, r)


def cmd_perfil(db, args):
    r = storage.find_location(db, args.alvo)
    raw = storage.latest_raw(r["id"])
    if not raw:
        sys.exit(f"{r['title']} ainda nao foi coletado. Rode 'coletar'.")
    print(json.dumps(normalize(raw), indent=2, ensure_ascii=False))


def cmd_retroativas(db, _):
    created, existing, ignored = backfill_retroactive(db)
    print(f"{created} analises retroativas criadas, {existing} coletas ja tinham analise"
          + (f", {ignored} ignoradas (local desconhecido)" if ignored else "") + ".")


def _gravar_pdf(render, report, args):
    for w in report["warnings"]:
        print(f"ATENCAO: {w}")
    pasta = args.saida or os.path.join(storage.DATA, "relatorios")
    try:
        path = html_to_pdf(render(report), os.path.join(pasta, report["filename"]))
    except PdfError as e:
        sys.exit(f"Nao foi possivel gerar o PDF: {e}")
    print(f"Relatorio gerado: {path}")


def cmd_relatorio(db, args):
    r = storage.find_location(db, args.alvo)
    try:
        report = build_report(db, r["id"], summary=args.resumo, analysis_id=args.analise)
    except ReportError as e:
        sys.exit(str(e))
    _gravar_pdf(render_html, report, args)


def cmd_diagnostico(db, args):
    """Imprime o diagnostico em JSON (so o JSON na saida padrao; avisos vao para a saida de erro)."""
    r = storage.find_location(db, args.alvo)
    if args.analisar:
        try:
            run_analysis(db, r)
        except AnalysisError as e:
            sys.exit(f"Nao foi possivel analisar agora: {e}")
        print(f"Analise real nova gravada para {r['title']}.", file=sys.stderr)
    try:
        data = diagnostico.build(db, r["id"])
    except LookupError as e:
        sys.exit(str(e))
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_comparativo(db, args):
    try:
        report = build_comparison_report(db, args.a, args.b)
    except ReportError as e:
        sys.exit(str(e))
    _gravar_pdf(render_comparison_html, report, args)


def cmd_relatorio_pre(db, args):
    try:
        report = build_pre_report(db, args.id, summary=args.resumo)
    except ReportError as e:
        sys.exit(str(e))
    _gravar_pdf(render_html, report, args)


def cmd_calibrar(db, args):
    manual = {}
    for pair in args.map or []:
        arquivo, sep, alvo = pair.partition("=")
        if not sep or not alvo:
            sys.exit(f"--map espera NOME=<alvo>, recebi '{pair}'")
        manual[arquivo.strip()] = storage.find_location(db, alvo.strip())
    calibrate(db, args.dir, manual, args.top, include_history=args.incluir_historico,
              only_divergences=args.so_divergencias)


def cmd_calibrar_pre(_db, args):
    calibrate_pre(args.arquivo, only_divergences=args.so_divergencias)


def cmd_segredo_extensao(_db, args):
    if gbp_auth.project_env().get("GBP_EXTENSION_SECRET") and not args.novo:
        sys.exit("Ja existe um segredo no .env. Use --novo para trocar (a extensao precisara do novo valor).")
    secret = secrets.token_urlsafe(32)
    gbp_auth.save_env_value("GBP_EXTENSION_SECRET", secret)
    print(f"Segredo gravado em {gbp_auth.ENV_PATH}. Cole-o agora nas opcoes da extensao SealsPro (ele nao e mostrado de novo):")
    print(secret)


def cmd_id_extensao(_db, args):
    ext_id = args.id.strip()
    if not re.fullmatch(r"[a-p]{32}", ext_id):
        sys.exit("ID invalido: sao 32 letras de a a p (veja em chrome://extensions, com o modo de desenvolvedor).")
    gbp_auth.save_env_value("GBP_EXTENSION_ID", ext_id)
    print(f"ID da extensao gravado em {gbp_auth.ENV_PATH}: {ext_id}")


def cmd_publicar(db, _):
    from posts.google_api import GoogleClient
    from posts.publisher import run_scheduled
    for line in run_scheduled(db, GoogleClient()):
        print(line)


def cmd_publicador(_db, args):
    from posts import launchd
    from posts.publisher import last_run
    if args.acao == "instalar":
        print(f"Agendador ligado: {launchd.install()}")
    elif args.acao == "remover":
        print(f"Agendador desligado: {launchd.uninstall()}")
    else:
        ultima = last_run()
        print(f"Instalado: {'sim' if launchd.installed() else 'nao'} · carregado: {'sim' if launchd.loaded() else 'nao'}"
              f" · ultima passada: {ultima.isoformat() if ultima else 'nunca'}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sincronizar").set_defaults(fn=cmd_sincronizar)
    sub.add_parser("locais").set_defaults(fn=cmd_locais)
    for nome, ativo in (("ativar", True), ("desativar", False)):
        s = sub.add_parser(nome)
        s.add_argument("alvo")
        s.set_defaults(fn=lambda db, a, ativo=ativo: cmd_ativar(db, a, ativo))
    c = sub.add_parser("coletar")
    c.add_argument("alvo", nargs="?")
    c.add_argument("--todos", action="store_true", help="todos os locais ativos")
    c.set_defaults(fn=cmd_coletar)
    sub.add_parser("retroativas").set_defaults(fn=cmd_retroativas)
    rel = sub.add_parser("relatorio")
    rel.add_argument("alvo", help="locations/ID ou parte do nome")
    rel.add_argument("--saida", help="pasta de destino (padrao: data/relatorios)")
    rel.add_argument("--resumo", action="store_true", help="so a nota e os itens fechados, sem orientacao")
    rel.add_argument("--analise", type=int, help="id de uma analise real do historico (padrao: a ultima)")
    rel.set_defaults(fn=cmd_relatorio)
    dg = sub.add_parser("diagnostico")
    dg.add_argument("alvo", help="locations/ID ou parte do nome")
    dg.add_argument("--analisar", action="store_true", help="faz uma analise real nova antes (usa a API do Google)")
    dg.set_defaults(fn=cmd_diagnostico)
    cp = sub.add_parser("comparativo")
    cp.add_argument("a", type=int, help="id de uma analise real (a mais antiga das duas vira o antes)")
    cp.add_argument("b", type=int, help="id da outra analise real do mesmo local")
    cp.add_argument("--saida", help="pasta de destino (padrao: data/relatorios)")
    cp.set_defaults(fn=cmd_comparativo)
    rp = sub.add_parser("relatorio-pre")
    rp.add_argument("id", type=int, help="id da pre analise (o numero em /pre?id=)")
    rp.add_argument("--saida", help="pasta de destino (padrao: data/relatorios)")
    rp.add_argument("--resumo", action="store_true", help="so a nota e os itens fechados, sem orientacao")
    rp.set_defaults(fn=cmd_relatorio_pre)
    k = sub.add_parser("calibrar")
    k.add_argument("--dir", help="pasta com as referencias (padrao: data/reference)")
    k.add_argument("--map", action="append", metavar="NOME=ALVO",
                   help="forca o local de uma referencia: NOME e o nome do local no arquivo (ou o nome do arquivo); ALVO e locations/ID ou parte do nome. Pode repetir")
    k.add_argument("--top", type=int, default=5, help="quantos itens no resumo (padrao 5)")
    k.add_argument("--incluir-historico", action="store_true",
                   help="compara tambem as versoes antigas do mesmo arquivo (padrao: so a de data mais recente)")
    k.add_argument("--so-divergencias", action="store_true",
                   help="nao imprime a tabela completa de cada local, so as divergencias, os valores brutos e o resumo")
    k.set_defaults(fn=cmd_calibrar)
    kp = sub.add_parser("calibrar-pre")
    kp.add_argument("--arquivo", help="referencia da Pre Analise (padrao: data/reference/pre_analises_original.json)")
    kp.add_argument("--so-divergencias", action="store_true",
                    help="nao imprime a tabela de todos os casos, so as divergencias e o resumo")
    kp.set_defaults(fn=cmd_calibrar_pre)
    se = sub.add_parser("segredo-extensao")
    se.add_argument("--novo", action="store_true", help="troca o segredo que ja existe")
    se.set_defaults(fn=cmd_segredo_extensao)
    ie = sub.add_parser("id-extensao")
    ie.add_argument("id")
    ie.set_defaults(fn=cmd_id_extensao)
    sub.add_parser("publicar").set_defaults(fn=cmd_publicar)
    pb = sub.add_parser("publicador")
    pb.add_argument("acao", choices=["instalar", "remover", "status"])
    pb.set_defaults(fn=cmd_publicador)
    s = sub.add_parser("perfil")
    s.add_argument("alvo")
    s.set_defaults(fn=cmd_perfil)
    args = p.parse_args()
    db = storage.connect()
    args.fn(db, args)


if __name__ == "__main__":
    main()
