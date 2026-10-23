"""PDF da Pre Analise (report/build_pre.py, report/texts_pre.py): textos, montagem, HTML, rota, linha de comando e o
PDF de verdade (pula sem Chrome)."""

import io
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from starlette.testclient import TestClient

import coletar
import storage
from report import render, texts_pre
from report.build import ReportError
from report.build_pre import build_pre_report
from report.pdf import find_chrome, html_to_pdf
from scoring.pre import analyze, version
from scoring.pre.items import ITEMS
from tests.scoring.pre.helpers import profile
from tests.test_report import FAKE_PDF, FORBIDDEN_IN_ADVICE, JARGON, fake_html_to_pdf
from web import app as webapp
from web import pre as pre_web

HAS_CHROME = find_chrome() is not None

# Perfis que, juntos, levam cada item a todos os estados possiveis (bom, razoavel, fraco e as variantes sem dado).
VARIANTS = [
    {},
    {"location__name": "x" * 120, "location__website": "https://www.instagram.com/exemplo/",
     "location__description": "x" * 60, "location__socialLinks": [], "posts__lastPostDays": 20,
     "media__lastOwnerPhotoDays": 45, "media__videos": 2, "reviews__count": 2, "reviews__average": 4.2,
     "reviews__lastReviewDays": 45, "reviews__sample__unanswered": 10, "reviews__sample__withText": 20},
    {"location__phone": "", "location__website": "", "location__hours": {}, "location__description": "x" * 30,
     "location__logoUrl": "", "location__verified": False, "posts__lastPostDays": 80,
     "media__lastOwnerPhotoDays": 90, "media__videos": 0, "media__photos360": 1, "reviews__count": 1,
     "reviews__average": 3.5, "reviews__lastReviewDays": 90, "reviews__sample__recentAverage": 3.0,
     "reviews__sample__unanswered": 30, "reviews__sample__withText": 5,
     "competitors__inTop10ByReviews": False, "competitors__averageReviews": 100},
    {"location__description": "", "posts__count": 0, "media__lastOwnerPhotoDays": None, "reviews__count": 0},
    {"reviews__sample__unanswered": 2, "reviews__sample__recentAverage": 4.5},
]


def all_described():
    for changes in VARIANTS:
        for item in analyze(profile(**changes))["items"]:
            yield item["id"], item["status"], texts_pre.describe(item["id"], item["status"], item["message"]["vars"])


class TextsTest(unittest.TestCase):
    def test_os_20_itens_do_motor_tem_titulo_e_texto(self):
        self.assertEqual(set(texts_pre.TITLES), {i.id for i in ITEMS})
        self.assertEqual(len(set(texts_pre.TITLES.values())), 20)

    def test_todos_os_estados_aparecem_nas_variantes(self):
        seen = {(i, s) for i, s, _ in all_described()}
        for item in ITEMS:
            self.assertIn((item.id, "good"), seen)
            self.assertTrue({(item.id, "fair"), (item.id, "bad")} & seen, item.id)

    def test_nenhum_texto_vazio_ou_com_variavel_sobrando(self):
        for item_id, status, (title, situation, advice, kind) in all_described():
            for text in (title, situation, advice):
                self.assertTrue(text.strip(), (item_id, status))
                self.assertNotRegex(text, r"[{}]|None", (item_id, status, text))
            self.assertEqual(kind, "manter" if status == "good" else "fazer")

    def test_orientacao_nao_promete_prazo_nem_resultado(self):
        for item_id, status, (_, _, advice, _) in all_described():
            for word in FORBIDDEN_IN_ADVICE:
                self.assertNotIn(word, advice.lower(), (item_id, word))

    def test_sem_jargao_tecnico(self):
        for item_id, status, texts in all_described():
            for text in texts:
                for word in JARGON:
                    self.assertIsNone(re.search(rf"\b{re.escape(word)}\b", text), (item_id, word, text))

    def test_numeros_aparecem_na_situacao(self):
        d = texts_pre.describe
        self.assertIn("2 de 3 vídeos", d("videos", "fair", {"current": 2, "recommended": 3})[1])
        self.assertIn("4,2 estrelas", d("reviews_average", "fair", {"current": 4.2, "recommended": 4.5})[1])
        self.assertIn("10 de 40 avaliações analisadas (25%)",
                      d("reviews_unanswered", "fair", {"current": 10, "size": 40, "percent": 25.0, "recommended": 10})[1])
        self.assertIn("média de 74 dos",
                      d("above_segment_average", "good", {"current": 464, "average": 74.1, "competitors": 48})[1])
        self.assertIn("há 1 dia.", d("last_post", "good", {"current": 1, "recommended": 15})[1])

    def test_frase_dos_contadores_no_singular_e_no_plural(self):
        _, second = texts_pre.overall_sentences("fair", {"good": 14, "fair": 1, "bad": 5})
        self.assertEqual(second, "Dos 20 itens avaliados, 14 estão em bom estado, 1 pode melhorar e 5 precisam de atenção.")
        self.assertIn("1 está em bom estado", texts_pre.overall_sentences("bad", {"good": 1, "fair": 2, "bad": 1})[1])
        self.assertIn("1 precisa de atenção", texts_pre.overall_sentences("good", {"good": 9, "fair": 0, "bad": 1})[1])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(storage, "DATA", self.tmp.name),
                  mock.patch.object(storage, "DB", os.path.join(self.tmp.name, "t.db"))):
            p.start()
            self.addCleanup(p.stop)
        self.db = storage.connect()
        self.addCleanup(self.db.close)

    def save(self, prof=None, engine=None, **changes):
        prof = prof or profile(**changes)
        result = analyze(prof)
        return storage.save_pre_analysis(self.db, prof, result, "", engine or version.PRE_ENGINE_VERSION,
                                         version.config_hash(), version.config_json())


class BuildTest(Base):
    def test_itens_do_pior_para_o_melhor_e_nome_do_arquivo(self):
        aid = self.save(location__verified=False, media__videos=2)
        r = build_pre_report(self.db, aid)
        self.assertEqual([g["status"] for g in r["groups"]], ["bad", "fair", "good"])
        self.assertEqual(r["groups"][0]["items"][0]["title"], "Perfil verificado")
        self.assertEqual(sum(len(g["items"]) for g in r["groups"]), 20)
        self.assertEqual(r["filename"], "Pre-Analise-negocio-exemplo-2026-07-08.pdf")  # 09/07 00h UTC = 08/07 em Brasilia
        self.assertEqual(r["date"], "08/07/2026")
        self.assertEqual(r["warnings"], [])

    def test_resumo_dos_concorrentes(self):
        r = build_pre_report(self.db, self.save(competitors__averageReviews=55.6, competitors__inTop10ByReviews=False))
        self.assertEqual(r["competitors"], {"count": 80, "average": 56, "reviews": 40, "top10": False, "above": False})

    def test_sem_concorrentes_o_resumo_some_e_os_itens_vao_para_nao_avaliados(self):
        r = build_pre_report(self.db, self.save(competitors=None))
        self.assertIsNone(r["competitors"])
        self.assertEqual({s["title"] for s in r["skipped"]},
                         {"Entre os 10 mais avaliados da região", "Avaliações frente aos concorrentes"})
        self.assertIn("2 itens não puderam ser avaliado(s)", r["warnings"][0])

    def test_faltando_3_ou_mais_avisa_para_conferir(self):
        r = build_pre_report(self.db, self.save(media=None))
        self.assertIn("Faltam 3 de 20 itens", r["warnings"][0])

    def test_avisos_da_coleta_e_versao_anterior(self):
        r = build_pre_report(self.db, self.save(engine="1", warnings=["leitor desatualizado"]))
        self.assertTrue(any("avisos" in w for w in r["warnings"]))
        self.assertTrue(any("versão anterior" in w for w in r["warnings"]))

    def test_pre_analise_inexistente_ou_sem_nota(self):
        with self.assertRaisesRegex(ReportError, "não encontrada"):
            build_pre_report(self.db, 999)
        p = profile()
        result = {"location": {"name": "X"}, "overall": {"score": None, "good": 0, "fair": 0, "bad": 0,
                                                         "unavailable": 20, "notApplicable": 0},
                  "items": [], "warnings": [], "analyzedAt": "2026-07-09T00:00:00+00:00"}
        p["location"] = {"name": "X"}
        aid = storage.save_pre_analysis(self.db, p, result, "", version.PRE_ENGINE_VERSION, version.config_hash(), "{}")
        with self.assertRaisesRegex(ReportError, "Nenhum item"):
            build_pre_report(self.db, aid)


class RenderTest(Base):
    def html(self, **changes):
        return render.render_html(build_pre_report(self.db, self.save(**changes)))

    def test_secoes_e_rotulos_da_pre(self):
        h = self.html(location__verified=False)
        for needle in ("Diagnóstico do perfil no Google", "Pré-análise realizada em 08/07/2026",
                       "SealsPro · Pré-análise de 08/07/2026", "Resumo da análise", "Comparação com a concorrência",
                       "Média de avaliações do segmento", "Entre os 10 mais avaliados", "Itens analisados",
                       "O que fazer", "Critérios próprios da SealsPro"):
            self.assertIn(needle, h)
        self.assertNotIn("Evolução da nota", h)
        self.assertNotIn("Não avaliados nesta análise", h)

    def test_contadores_mostram_os_numeros(self):
        h = self.html(location__verified=False, media__videos=2)
        for key, n in (("bad", 1), ("fair", 1), ("good", 18)):
            self.assertRegex(h, rf'class="counter st-{key}"><strong>{n}</strong>')

    def test_nota_so_na_geral_e_nunca_por_item(self):
        h = self.html()
        self.assertEqual(h.count("de 100"), 2)
        for block in re.findall(r'<article class="item.*?</article>', h, re.S):
            self.assertNotRegex(block, r"\b\d{1,3}\s*(/|de)\s*100\b")

    def test_texto_capturado_sai_escapado(self):
        h = self.html(location__name="<script>alert(1)</script>", location__website="https://x.com/<b>y</b>")
        self.assertNotIn("<script>alert(1)", h)
        self.assertNotIn("<b>y</b>", h)

    def test_nada_e_carregado_da_internet(self):
        h = self.html()
        self.assertEqual(re.findall(r'(?:src|href)="https?://', h), [])
        self.assertEqual(re.findall(r'url\(\s*["\']?https?://', h), [])


class SummaryTest(Base):
    """PDF resumido: so a nota e os itens fechados, sem orientacao; titulo dos itens com problema nao entra no arquivo."""

    def report(self, **changes):
        changes = changes or {"location__verified": False, "media__videos": 2}
        return build_pre_report(self.db, self.save(**changes), summary=True)

    def test_itens_fechados_sem_orientacao(self):
        r = self.report()
        h = render.render_html(r)
        for needle in ("O que fazer", "Como manter", "Comparação com a concorrência", '<article class="item'):
            self.assertNotIn(needle, h)
        self.assertIn("Itens analisados", h)
        self.assertIn("Quer saber o que ajustar?", h)
        items = [i for g in r["groups"] for i in g["items"]]
        self.assertEqual(h.count('<div class="row st-'), len(items))
        for i in items:
            if i["status"] == "good":
                self.assertIn(i["title"], h)
            else:
                self.assertNotIn(i["title"], h)  # nem escondido: o titulo real nao vai para o arquivo
        self.assertEqual(h.count('class="t hidden"'), r["counts"]["bad"] + r["counts"]["fair"])

    def test_tudo_bom_nao_tem_convite(self):
        r = build_pre_report(self.db, self.save(), summary=True)
        if r["counts"]["bad"] + r["counts"]["fair"] == 0:
            self.assertNotIn("Quer saber o que ajustar?", render.render_html(r))

    def test_mascara_tem_o_tamanho_do_titulo(self):
        self.assertEqual(len(render.mask("Perfil verificado")), len("Perfil verificado"))
        self.assertNotIn("verificado", render.mask("Perfil verificado"))

    @unittest.skipUnless(HAS_CHROME, "Chrome nao encontrado")
    def test_pdf_resumido_de_verdade(self):
        from pypdf import PdfReader
        r = self.report()
        path = os.path.join(self.tmp.name, "resumo.pdf")
        html_to_pdf(render.render_html(r), path)
        text = "\n".join(p.extract_text() for p in PdfReader(path).pages).lower().replace("\ufb01", "fi").replace("\ufb02", "fl")
        self.assertIn("resumo da análise", text)
        self.assertNotIn("lorem", text)  # o borrado sai como imagem: nem o texto neutro fica selecionavel
        self.assertNotIn("o que fazer", text)
        for i in (i for g in r["groups"] for i in g["items"]):
            (self.assertIn if i["status"] == "good" else self.assertNotIn)(i["title"].lower(), text)


class RoutesTest(Base):
    def setUp(self):
        super().setUp()
        self.client = TestClient(webapp.app, base_url="http://127.0.0.1:8000")

    def test_baixar_pdf(self):
        aid = self.save()
        with mock.patch("report.pdf.html_to_pdf", fake_html_to_pdf):
            r = self.client.get(f"/pre/relatorio.pdf?id={aid}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, FAKE_PDF)
        self.assertIn('filename="Pre-Analise-negocio-exemplo-2026-07-08.pdf"', r.headers["content-disposition"])

    def test_pre_analise_inexistente(self):
        r = self.client.get("/pre/relatorio.pdf?id=999")
        self.assertEqual(r.status_code, 404)
        self.assertIn("não encontrada", r.text)

    def test_um_pdf_por_vez_compartilhado_com_a_completa(self):
        aid = self.save()
        self.assertIs(webapp._report_lock, pre_web.report_pdf.LOCK)
        webapp._report_lock.acquire()
        try:
            r = self.client.get(f"/pre/relatorio.pdf?id={aid}")
        finally:
            webapp._report_lock.release()
        self.assertEqual(r.status_code, 409)

    def test_menu_de_acoes_e_avisos_so_na_tela(self):
        aid = self.save()
        ok = self.client.get(f"/pre?id={aid}").text
        self.assertIn(f'href="/pre/relatorio.pdf?id={aid}"', ok)
        self.assertIn(f'href="/pre/relatorio.pdf?id={aid}&amp;modo=resumo"', ok)
        self.assertIn(f'href="/simulador?pre={aid}"', ok)
        self.assertNotIn("confirm(", ok)
        incomplete = self.client.get(f"/pre?id={self.save(media=None)}").text
        self.assertNotIn("confirm(", incomplete)  # o PDF sai direto; o aviso fica na tela
        self.assertIn("Faltam 3 de 20 itens", incomplete)

    def test_pdf_resumido_pela_rota(self):
        aid = self.save()
        with mock.patch("report.pdf.html_to_pdf", fake_html_to_pdf):
            r = self.client.get(f"/pre/relatorio.pdf?id={aid}&modo=resumo")
        self.assertEqual(r.status_code, 200)
        self.assertIn('filename="Pre-Analise-Resumo-negocio-exemplo-', r.headers["content-disposition"])

    def test_falha_do_chrome_mostra_mensagem(self):
        from report.pdf import PdfError
        aid = self.save()
        with mock.patch("report.pdf.html_to_pdf", side_effect=PdfError("sem chrome")):
            r = self.client.get(f"/pre/relatorio.pdf?id={aid}")
        self.assertEqual(r.status_code, 500)
        self.assertIn("Não foi possível gerar o PDF", r.text)


class CliTest(Base):
    def test_gera_na_pasta_escolhida_e_mostra_avisos(self):
        aid = self.save(media=None)
        out = os.path.join(self.tmp.name, "saida")
        buf = io.StringIO()
        with mock.patch.object(coletar, "html_to_pdf", fake_html_to_pdf), redirect_stdout(buf):
            coletar.cmd_relatorio_pre(self.db, mock.Mock(id=aid, saida=out, resumo=False))
        self.assertTrue(os.path.isfile(os.path.join(out, "Pre-Analise-negocio-exemplo-2026-07-08.pdf")))
        self.assertIn("ATENCAO: Faltam 3", buf.getvalue())

    def test_inexistente_sai_com_mensagem(self):
        with self.assertRaises(SystemExit) as e:
            coletar.cmd_relatorio_pre(self.db, mock.Mock(id=999, saida=None, resumo=False))
        self.assertIn("não encontrada", str(e.exception))


@unittest.skipUnless(HAS_CHROME, "Chrome nao encontrado")
class PdfTest(Base):
    def test_pdf_de_verdade(self):
        from pypdf import PdfReader
        aid = self.save(location__verified=False, competitors=None)
        path = os.path.join(self.tmp.name, "pre.pdf")
        html_to_pdf(render.render_html(build_pre_report(self.db, aid)), path)
        reader = PdfReader(path)
        n = len(reader.pages)
        self.assertGreaterEqual(n, 4)
        text = "\n".join(p.extract_text() for p in reader.pages).lower()
        for needle in ("negócio exemplo", "diagnóstico do perfil no google", "resumo da análise", "itens analisados",
                       "o que fazer", "como manter", "critérios próprios da sealspro"):
            self.assertIn(needle, text)
        self.assertNotIn("não avaliados nesta análise", text)  # problemas ficam so na tela
        for i, page in enumerate(reader.pages, 1):
            w, h = (float(x) for x in page.mediabox[2:])
            self.assertAlmostEqual(w, 595.3, delta=1.5)
            self.assertIn(f"Página {i} de {n}", page.extract_text())
            self.assertIn("SealsPro · Pré-análise de", page.extract_text())
