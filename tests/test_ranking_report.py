"""PDF da Analise de Ranking (CLAUDE.md, 16, fase R5): montagem, mapa (sem internet nos testes), evolucao, escape de
nomes vindos do Maps e o PDF de verdade (pula sem Chrome)."""

import base64
import os
import tempfile
import unittest
from contextlib import closing
from unittest import mock

import storage
from report import build_ranking, pdf as report_pdf
from report.build import ReportError
from report.build_ranking import build_ranking_report, static_map
from report.pdf import find_chrome, html_to_pdf
from report.render import render_ranking_comparison_html, render_ranking_html
from tests.test_ranking import CLIENT_CID, LOC, XSS, HistoryTest, place, search
from tests.test_report import FAKE_PDF, fake_html_to_pdf

HAS_CHROME = find_chrome() is not None
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def no_internet(z, x, y):
    return None


def tile(z, x, y):
    return PNG


class StaticMapTest(unittest.TestCase):
    def test_pontos_cabem_no_mapa(self):
        pts = [{"lat": -19.95 + 0.01 * (i // 5), "lng": -43.95 + 0.01 * (i % 5)} for i in range(25)]
        m = static_map(pts, fetch=tile)
        self.assertTrue(m["has_tiles"])
        for p in m["points"]:
            self.assertTrue(0 < p["x"] < m["width"] and 0 < p["y"] < m["height"], p)
        # norte em cima: o ponto de maior latitude fica mais acima
        self.assertLess(m["points"][24]["y"], m["points"][0]["y"])
        self.assertTrue(m["tiles"][0]["src"].startswith("data:image/png;base64,"))

    def test_sem_internet_fica_so_a_grade(self):
        m = static_map([{"lat": 0, "lng": 0}, {"lat": 0.01, "lng": 0.01}], fetch=no_internet)
        self.assertEqual((m["tiles"], m["has_tiles"]), ([], False))
        self.assertEqual(len(m["points"]), 2)


class RankingReportTest(HistoryTest):
    def ready(self, own_at=None, name="Rival"):
        return self.run_ranking(own_at or [None] * 4 + [2] + [None] * 4)

    def test_monta_o_relatorio(self):
        rid = self.ready()
        with closing(storage.connect()) as db:
            rep = build_ranking_report(db, rid, fetch=no_internet)
        self.assertEqual((rep["own"]["found"], rep["own"]["points"]), (1, 9))
        self.assertEqual(len(rep["cells"]), 9)
        self.assertEqual(rep["cells"][4]["pos"], 2)
        self.assertIsNone(rep["evolution"])  # uma analise so
        self.assertTrue(rep["filename"].startswith("Ranking-clinica-exemplo-"))
        html = render_ranking_html(rep)
        self.assertIn("Onde o perfil aparece", html)
        self.assertIn("Quem aparece na frente", html)
        self.assertIn("Critérios próprios da SealsPro", html)
        self.assertNotIn("OpenStreetMap", html)  # sem fundo, sem atribuicao

    def test_nome_do_maps_escapado(self):
        rid = self.create()
        self.ext("/ranking/inicio", {"place": self.place})
        for i in range(9):
            self.ext("/ranking/ponto", {"id": rid, "i": i, "text": search(place(61, XSS))})
        self.ext("/ranking/fim", {"id": rid})
        with closing(storage.connect()) as db:
            html = render_ranking_html(build_ranking_report(db, rid, fetch=no_internet))
        self.assertNotIn(XSS, html)
        self.assertIn("&lt;script&gt;", html)

    def test_evolucao_so_com_duas_datas(self):
        a = self.ready([None] * 9)
        b = self.ready()
        with closing(storage.connect()) as db:
            self.assertIsNone(build_ranking_report(db, b, fetch=no_internet)["evolution"])  # mesmo dia
            db.execute("UPDATE rankings SET created_at='2026-09-01T12:00:00+00:00' WHERE id=?", (a,))
            db.commit()
            rep = build_ranking_report(db, b, fetch=no_internet)
            self.assertEqual(rep["evolution"]["n"], 2)
            self.assertIn("Evolução", render_ranking_html(rep))
            # o PDF da analise antiga nao mostra o que veio depois
            self.assertIsNone(build_ranking_report(db, a, fetch=no_internet)["evolution"])

    def test_pontos_desligados_no_pdf(self):
        rid = self.ready()
        self.client.post(f"/ranking/pontos?id={rid}", content='{"disabled": [0, 1]}',
                         headers={"content-type": "application/json", "origin": "http://127.0.0.1:8000"})
        with closing(storage.connect()) as db:
            rep = build_ranking_report(db, rid, fetch=no_internet)
        self.assertEqual([c["off"] for c in rep["cells"][:3]], [True, True, False])
        self.assertEqual(rep["own"]["points"], 7)
        self.assertEqual(render_ranking_html(rep).count('class="pin poff"'), 2)

    def test_so_analise_pronta(self):
        rid = self.create()
        with closing(storage.connect()) as db:
            with self.assertRaises(ReportError):
                build_ranking_report(db, rid, fetch=no_internet)
            with self.assertRaises(ReportError):
                build_ranking_report(db, 999, fetch=no_internet)

    def test_rota_do_pdf(self):
        rid = self.ready()
        with mock.patch.object(build_ranking, "fetch_tile", no_internet), \
                mock.patch.object(report_pdf, "html_to_pdf", fake_html_to_pdf):
            r = self.client.get(f"/ranking/relatorio.pdf?id={rid}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, FAKE_PDF)
        self.assertIn("attachment", r.headers["content-disposition"])
        self.assertIn("Baixar PDF", self.client.get(f"/ranking/analise?id={rid}").text)
        self.assertEqual(self.client.get(f"/ranking/relatorio.pdf?id={self.create()}").status_code, 409)

    @unittest.skipUnless(HAS_CHROME, "sem Chrome")
    def test_pdf_de_verdade(self):
        rid = self.ready()
        with closing(storage.connect()) as db:
            rep = build_ranking_report(db, rid, fetch=tile)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, rep["filename"])
            html_to_pdf(render_ranking_html(rep), out)
            from pypdf import PdfReader
            reader = PdfReader(out)
            text = "".join(p.extract_text() for p in reader.pages)
        self.assertGreaterEqual(len(reader.pages), 3)
        self.assertIn("Onde o perfil aparece", text)
        self.assertIn("Ranking de", text)  # rodape


if __name__ == "__main__":
    unittest.main()


class RankingComparisonReportTest(HistoryTest):
    def test_monta_o_comparativo(self):
        a = self.run_ranking([None] * 9)
        b = self.run_ranking([None] * 4 + [1] + [None] * 3 + [2])
        with closing(storage.connect()) as db:
            rep = build_ranking.build_ranking_comparison_report(db, b, a, fetch=no_internet)  # ordem trocada
        self.assertEqual(rep["sentence_1"], "O perfil passou a aparecer em 2 de 9 pontos (antes, 0).")
        self.assertEqual(rep["sentence_2"], "Em 2 pontos a posição melhorou.")
        found = rep["numbers"][0]
        self.assertEqual((found["before"], found["after"], found["delta"], found["trend"]), ("0 de 9", "2 de 9", "+2", "good"))
        self.assertIsNone(rep["evolution"])
        self.assertTrue(rep["filename"].startswith("Comparativo-Ranking-clinica-exemplo-"))
        html = render_ranking_comparison_html(rep)
        self.assertIn("Antes e depois", html)
        self.assertIn("Quem aparece na frente agora", html)
        self.assertEqual(html.count('class="ch-better"'), 2)

    def test_evolucao_com_tres_analises_no_periodo(self):
        ids = [self.run_ranking([None] * 9) for _ in range(3)]
        with closing(storage.connect()) as db:
            rep = build_ranking.build_ranking_comparison_report(db, ids[0], ids[2], fetch=no_internet)
        self.assertEqual(rep["evolution"]["n"], 3)
        self.assertIn("Evolução no período", render_ranking_comparison_html(rep))

    def test_recusa_series_diferentes_e_escapa_nomes(self):
        a = self.run_ranking([None] * 9)
        b = self.run_ranking([None] * 9, keyword="ortodontista")
        with closing(storage.connect()) as db:
            with self.assertRaises(ReportError):
                build_ranking.build_ranking_comparison_report(db, a, b, fetch=no_internet)
            with self.assertRaises(ReportError):
                build_ranking.build_ranking_comparison_report(db, a, a, fetch=no_internet)
        c = self.create()
        self.ext("/ranking/inicio", {"place": self.place})
        for i in range(9):
            self.ext("/ranking/ponto", {"id": c, "i": i, "text": search(place(61, XSS))})
        self.ext("/ranking/fim", {"id": c})
        with closing(storage.connect()) as db:
            html = render_ranking_comparison_html(build_ranking.build_ranking_comparison_report(db, a, c, fetch=no_internet))
        self.assertNotIn(XSS, html)
        self.assertIn("&lt;script&gt;", html)

    def test_rota_e_botoes(self):
        a = self.run_ranking([None] * 9)
        b = self.run_ranking([None] * 4 + [1] + [None] * 4)
        with mock.patch.object(build_ranking, "fetch_tile", no_internet), \
                mock.patch.object(report_pdf, "html_to_pdf", fake_html_to_pdf):
            r = self.client.get(f"/ranking/comparativo.pdf?a={a}&b={b}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, FAKE_PDF)
        self.assertIn("Comparativo-Ranking-", r.headers["content-disposition"])
        self.assertIn(f"/ranking/comparativo.pdf?a={a}&amp;b={b}", self.client.get(f"/ranking/comparar?a={a}&b={b}").text)
        self.assertIn('formaction="/ranking/comparativo.pdf"', self.client.get(f"/ranking?local={LOC}").text)
        self.assertEqual(self.client.get(f"/ranking/comparativo.pdf?a={a}&b={a}").status_code, 409)

    @unittest.skipUnless(HAS_CHROME, "sem Chrome")
    def test_pdf_de_verdade(self):
        a = self.run_ranking([None] * 9)
        b = self.run_ranking([None] * 4 + [1] + [None] * 4)
        with closing(storage.connect()) as db:
            rep = build_ranking.build_ranking_comparison_report(db, a, b, fetch=tile)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, rep["filename"])
            html_to_pdf(render_ranking_comparison_html(rep), out)
            from pypdf import PdfReader
            text = "".join(p.extract_text() for p in PdfReader(out).pages)
        self.assertIn("Antes e depois", text)
        self.assertIn("Comparativo de ranking", text)  # rodape
