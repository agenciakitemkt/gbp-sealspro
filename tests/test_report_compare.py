"""PDF comparativo (antes e depois) e PDF de uma analise do historico."""

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
from collector.normalize import normalize
from report import render
from report.build import ReportError, build_report
from report.build_compare import build_comparison_report
from report.pdf import html_to_pdf
from scoring import analyze
from tests.test_history import TempStorage
from tests.test_report import HAS_CHROME, JARGON, REVIEW_TEXT, fake_html_to_pdf, make_raw
from web import app as webapp

BEFORE = "2026-09-01T12:00:00+00:00"
AFTER = "2026-10-08T12:00:00+00:00"
MEDIA_ITEMS = {"Vídeos", "Logotipo", "Foto de capa"}


def raw_before(collected=BEFORE, **kw):
    """Perfil 'antes': sem nenhuma midia (logotipo, capa e video caem)."""
    return make_raw(collected, media=[], **kw)


def raw_after(collected=AFTER, **kw):
    """Perfil 'depois': mais avaliacoes e com as midias."""
    raw = make_raw(collected, **kw)
    extra = [{"starRating": "FIVE", "comment": "bom", "createTime": "2026-10-0%dT00:00:00Z" % d,
              "reviewReply": {"comment": "obrigado"}} for d in range(1, 6)]
    raw["reviews"] = raw["reviews"] + extra
    raw["reviewsSummary"] = {"averageRating": 4.8, "totalReviewCount": len(raw["reviews"])}
    return raw


def score_of(raw):
    return analyze(normalize({**raw, "location": "locations/1"}))["overall"]["score"]


class CompareBuildTest(TempStorage):
    def pair(self, **kw_after):
        a = self.analysis(raw_before())
        b = self.analysis(raw_after(**kw_after))
        return a, b

    def test_antes_e_depois_em_ordem_cronologica_qualquer_que_seja_a_ordem_pedida(self):
        a, b = self.pair()
        for x, y in ((a, b), (b, a)):
            r = build_comparison_report(self.db, x, y)
            self.assertEqual((r["before_id"], r["after_id"]), (a, b))
            self.assertEqual((r["date_before"], r["date_after"]), ("01/09/2026", "08/10/2026"))
        self.assertEqual((r["before"]["score"], r["after"]["score"]), (score_of(raw_before()), score_of(raw_after())))
        self.assertEqual(r["delta"], r["after"]["score"] - r["before"]["score"])
        self.assertGreater(r["delta"], 0)

    def test_itens_que_melhoraram_e_que_pioraram(self):
        a, b = self.pair()
        items = build_comparison_report(self.db, a, b)["items"]
        improved = {i["title"] for i in items["improved"]}
        self.assertTrue(MEDIA_ITEMS <= improved, improved)
        self.assertEqual(items["worsened"], [])
        for i in items["improved"]:
            self.assertTrue(i["rose"] or i["change"], i)  # subiu de faixa ou teve mudanca para melhor
            self.assertTrue(i["situation"])
            self.assertNotIn("score", i)  # nunca a nota do item
        # ao contrario: os mesmos itens pioram
        c = self.analysis(raw_before("2026-10-10T12:00:00+00:00"))
        worse = {i["title"] for i in build_comparison_report(self.db, b, c)["items"]["worsened"]}
        self.assertTrue(MEDIA_ITEMS <= worse, worse)

    def test_todo_item_avaliado_nas_duas_aparece_em_uma_so_lista(self):
        a, b = self.pair()
        items = build_comparison_report(self.db, a, b)["items"]
        ids = [i["id"] for k in ("improved", "worsened", "still_low", "still_good") for i in items[k]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 21)

    def test_mesma_faixa_com_alteracao_aparece_como_melhorado(self):
        before = raw_after("2026-09-01T12:00:00+00:00")
        before["info"] = {**before["info"], "profile": {"description": "x" * 200}}
        after = raw_after()
        after["info"] = {**after["info"], "profile": {"description": "y" * 640}}
        after["media"] = [{**m, "name": "media/nova-logo"} if m["locationAssociation"]["category"] == "PROFILE" else m
                          for m in after["media"]]
        r = build_comparison_report(self.db, self.analysis(before), self.analysis(after))
        improved = {i["id"]: i for i in r["items"]["improved"]}
        self.assertEqual((improved["description"]["before"], improved["description"]["after"]), ("good", "good"))
        self.assertFalse(improved["description"]["rose"])
        self.assertIn("antes com 200 caracteres, agora com 640", improved["description"]["change"])
        self.assertEqual(improved["logo"]["change"], "O logotipo foi trocado.")
        kept = {i["id"] for i in r["items"]["still_good"]}
        self.assertFalse(kept & set(improved))
        self.assertIn("melhoraram", r["sentence_2"])

    def test_sem_alteracao_nada_aparece_como_melhorado(self):
        r = build_comparison_report(self.db, self.analysis(raw_after("2026-09-01T12:00:00+00:00")),
                                    self.analysis(raw_after()))
        self.assertEqual(r["items"]["improved"], [])
        self.assertEqual(r["sentence_2"], "Nenhum item mudou.")

    def test_retirar_nao_conta_e_faixa_que_caiu_continua_ponto_de_atencao(self):
        a = self.analysis(raw_after("2026-09-01T12:00:00+00:00"))
        b = self.analysis(raw_before())  # sem midias: logotipo, capa e videos caem
        r = build_comparison_report(self.db, a, b)
        self.assertNotIn("logo", {i["id"] for i in r["items"]["improved"]})
        self.assertIn("logo", {i["id"] for i in r["items"]["worsened"]})

    def test_respostas_e_postagens_novas(self):
        before = raw_after("2026-09-01T12:00:00+00:00")
        before["reviews"] = [{**rv, "reviewReply": None} for rv in before["reviews"]]
        after = raw_after()
        after["localPosts"] = after["localPosts"] + [{"topicType": "STANDARD", "createTime": "2026-10-07T15:00:00Z"}]
        r = build_comparison_report(self.db, self.analysis(before), self.analysis(after))
        changes = {i["id"]: i["change"] for k in ("improved", "worsened") for i in r["items"][k]}
        self.assertRegex(changes["reviews_unanswered"], r"^\d+ avaliações respondidas")
        self.assertEqual(changes["last_post"], "1 postagem nova publicada; a mais recente em 07/10/2026.")

    def test_bloco_das_fotos_de_clientes(self):
        after = raw_after()
        after["info"] = {**after["info"], "metadata": {
            **after["info"]["metadata"], "newReviewUri": "https://search.google.com/local/writereview?placeid=ChIJ-x"}}
        r = build_comparison_report(self.db, self.analysis(raw_before()), self.analysis(after))
        cp = r["customer_photos"]
        self.assertEqual((cp["current"], cp["recommended"], cp["missing"]), (0, 3, 3))
        self.assertEqual(cp["link"], "https://search.google.com/local/writereview?placeid=ChIJ-x")
        self.assertTrue(cp["whatsapp"].startswith("https://wa.me/?text="))
        self.assertIn("placeid%3DChIJ-x", cp["whatsapp"])
        h = render.render_comparison_html(r)
        for needle in ("Sua parte", "3 avaliações novas com foto", "Vale qualquer foto", "Família e amigos",
                       "o Google identificar que a avaliação é de um familiar ou amigo, ele pode removê-la",
                       "Acrescentar foto numa avaliação que já foi publicada não conta", "Compartilhar no WhatsApp",
                       'href="https://search.google.com/local/writereview?placeid=ChIJ-x"'):
            self.assertIn(needle, h)
        self.assertLess(h.index("Sua parte"), h.index("O que mudou nos itens"))  # antes dos itens, em destaque

    def test_bloco_das_fotos_some_quando_ja_tem_tres_e_sem_link_sem_dado(self):
        after = raw_after(mediaCustomers=[{"mediaFormat": "PHOTO", "createTime": f"2026-10-0{d}T00:00:00Z",
                                           "name": f"c{d}"} for d in (1, 2, 3)])
        self.assertIsNone(build_comparison_report(self.db, self.analysis(raw_before()),
                                                  self.analysis(after))["customer_photos"])
        r = build_comparison_report(self.db, self.analysis(raw_before("2026-09-02T12:00:00+00:00")),
                                    self.analysis(raw_after("2026-10-09T12:00:00+00:00")))
        self.assertIsNone(r["customer_photos"]["link"])
        self.assertNotIn("Compartilhar no WhatsApp", render.render_comparison_html(r))

    def test_item_nao_avaliado_em_uma_das_duas_fica_de_fora_com_aviso(self):
        a, b = self.pair(errors={"localPosts": "HTTP 500"})
        r = build_comparison_report(self.db, a, b)
        ids = [i["id"] for k in r["items"] for i in r["items"][k]]
        self.assertNotIn("last_post", ids)
        self.assertEqual(len(ids), 20)
        self.assertTrue(any("depois" in w and "fora do comparativo" in w for w in r["warnings"]), r["warnings"])

    def test_numeros_do_perfil(self):
        a, b = self.pair()
        rows = {n["label"]: n for n in build_comparison_report(self.db, a, b)["numbers"]}
        self.assertEqual((rows["Avaliações no Google"]["before"], rows["Avaliações no Google"]["after"]), ("3", "8"))
        self.assertEqual((rows["Avaliações no Google"]["delta"], rows["Avaliações no Google"]["trend"]), ("+5", "good"))
        self.assertEqual(rows["Vídeos"]["delta"], "+1")
        self.assertRegex(rows["Nota média"]["after"], r"^\d,\d$")
        self.assertEqual(rows["Avaliações sem resposta"]["trend"], "same")
        c = self.analysis(raw_after("2026-10-10T12:00:00+00:00", reviews=make_raw()["reviews"] + [
            {"starRating": "THREE", "createTime": "2026-10-09T00:00:00Z"}]))
        rows = {n["label"]: n for n in build_comparison_report(self.db, b, c)["numbers"]}
        unanswered = rows["Avaliações sem resposta"]
        self.assertEqual((unanswered["delta"], unanswered["trend"]), ("+1", "bad"))  # subir aqui e ruim

    def test_recalcula_as_duas_com_o_motor_atual(self):
        a = self.analysis(raw_before(), engine_version="0", config_hash="z" * 64)
        b = self.analysis(raw_after())
        r = build_comparison_report(self.db, a, b)
        self.assertEqual(r["before"]["score"], score_of(raw_before()))
        self.assertEqual(storage.get_analysis(self.db, a)["engine_version"], "0")  # nada e gravado

    def _drop_raw(self, analysis_id):
        os.remove(storage.get_analysis(self.db, analysis_id)["raw_path"])

    def test_sem_bruto_e_versao_atual_usa_a_nota_guardada_sem_os_numeros(self):
        a, b = self.pair()
        self._drop_raw(a)
        r = build_comparison_report(self.db, a, b)
        self.assertIsNone(r["numbers"])
        self.assertTrue(any("números do perfil" in w for w in r["warnings"]))

    def test_sem_bruto_e_versao_antiga_nao_compara(self):
        a = self.analysis(raw_before(), engine_version="0")
        b = self.analysis(raw_after())
        self._drop_raw(a)
        with self.assertRaisesRegex(ReportError, "mesmos critérios"):
            build_comparison_report(self.db, a, b)

    def test_so_analises_reais_do_mesmo_local(self):
        a = self.analysis(raw_before())
        retro = self.analysis(raw_after(), kind="retroativa")
        other = self.analysis(raw_after(), location="locations/2")
        with self.assertRaisesRegex(ReportError, "análise real"):
            build_comparison_report(self.db, a, retro)
        with self.assertRaisesRegex(ReportError, "análise real"):
            build_comparison_report(self.db, retro, a)
        with self.assertRaisesRegex(ReportError, "mesmo local"):
            build_comparison_report(self.db, a, other)
        with self.assertRaisesRegex(ReportError, "duas análises diferentes"):
            build_comparison_report(self.db, a, a)
        with self.assertRaisesRegex(ReportError, "não encontrada"):
            build_comparison_report(self.db, 999, a)

    def test_evolucao_so_com_tres_ou_mais_analises_no_periodo(self):
        a, b = self.pair()
        self.assertIsNone(build_comparison_report(self.db, a, b)["evolution"])
        self.analysis(raw_before("2026-09-20T12:00:00+00:00"))  # no meio
        self.analysis(raw_after("2026-10-20T12:00:00+00:00"))   # depois do periodo: fora
        evo = build_comparison_report(self.db, a, b)["evolution"]
        self.assertEqual(evo["count"], 3)

    def test_frases_e_nome_do_arquivo(self):
        a, b = self.pair()
        r = build_comparison_report(self.db, a, b)
        self.assertIn("A nota geral subiu de", r["sentence_1"])
        self.assertIn("melhorar", r["sentence_2"].replace("melhoraram", "melhorar").replace("melhorou", "melhorar"))
        self.assertEqual(r["filename"], "Comparativo-clinica-x-2026-09-01-a-2026-10-08.pdf")


class HistoricalReportTest(TempStorage):
    def test_pdf_de_uma_analise_antiga_com_a_evolucao_ate_ela(self):
        first = self.analysis(make_raw("2026-09-01T12:00:00+00:00"))
        mid = self.analysis(make_raw("2026-09-15T12:00:00+00:00"))
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"))
        r = build_report(self.db, "locations/1", analysis_id=mid)
        self.assertEqual((r["analysis_id"], r["date"]), (mid, "15/09/2026"))
        self.assertEqual(r["evolution"]["count"], 2)  # so ate 15/09
        self.assertEqual(r["filename"], "Relatorio-clinica-x-2026-09-15.pdf")
        self.assertIsNone(build_report(self.db, "locations/1", analysis_id=first)["evolution"])

    def test_retroativa_ou_de_outro_local_nao_gera(self):
        retro = self.analysis(make_raw(), kind="retroativa")
        other = self.analysis(make_raw(), location="locations/2")
        with self.assertRaisesRegex(ReportError, "análise real"):
            build_report(self.db, "locations/1", analysis_id=retro)
        with self.assertRaisesRegex(ReportError, "não encontrada"):
            build_report(self.db, "locations/1", analysis_id=other)


class CompareRenderTest(TempStorage):
    def html(self, raw_b=None):
        a = self.analysis(raw_before())
        b = self.analysis(raw_b or raw_after())
        return render.render_comparison_html(build_comparison_report(self.db, a, b))

    def test_secoes(self):
        h = self.html()
        for needle in ("Evolução do perfil no Google", "De 01/09/2026 a 08/10/2026", "Antes e depois",
                       "Números do perfil", "O que mudou nos itens", "Melhoraram", "Critérios próprios da SealsPro",
                       "SealsPro · Comparativo de 01/09/2026 a 08/10/2026", "Preparado pela SealsPro"):
            self.assertIn(needle, h)
        self.assertNotIn("Pontos de atenção", h)  # nenhum piorou

    def test_sem_orientacao_de_como_fazer_nem_nota_por_item(self):
        h = self.html()
        for forbidden in ("O que fazer", "Como manter", 'class="band"', 'class="advice'):
            self.assertNotIn(forbidden, h)

    def test_itens_que_pioraram_aparecem(self):
        a = self.analysis(raw_after("2026-09-01T12:00:00+00:00"))
        b = self.analysis(raw_before("2026-10-08T12:00:00+00:00"))
        h = render.render_comparison_html(build_comparison_report(self.db, a, b))
        self.assertIn("Pontos de atenção", h)

    def test_texto_de_avaliacao_nunca_aparece_e_nome_e_escapado(self):
        raw = raw_after()
        raw["info"] = {**raw["info"], "title": "<script>alert(1)</script>"}
        h = self.html(raw)
        self.assertNotIn(REVIEW_TEXT, h)
        self.assertNotIn("<script>alert(1)", h)
        self.assertIn("&lt;script&gt;", h)

    def test_contadores_com_frase_completa(self):
        h = self.html()
        for phrase in ("itens que precisam de atenção", "itens que podem melhorar", "itens que estão em ótimo estado"):
            self.assertIn(phrase, h)

    def test_sem_jargao_e_nada_da_internet(self):
        h = self.html()
        text = re.sub(r"<style>.*?</style>|<[^>]+>", " ", h, flags=re.S)
        for word in JARGON:
            self.assertIsNone(re.search(rf"\b{re.escape(word)}\b", text), word)
        self.assertIsNone(re.search(r"src=\"https?://", h))
        # links clicaveis so para avaliar no Google e compartilhar no WhatsApp (nada e carregado da internet)
        for link in re.findall(r"href=\"(https?://[^\"]+)", h):
            self.assertRegex(link, r"^https://(search\.google\.com/local/writereview|wa\.me/)")
        self.assertNotIn("url(\"http", h)


class CompareRoutesTest(TempStorage):
    def setUp(self):
        super().setUp()
        self.client = TestClient(webapp.app, base_url="http://127.0.0.1:8000")

    def test_baixar_comparativo(self):
        a, b = self.analysis(raw_before()), self.analysis(raw_after())
        with mock.patch.object(webapp, "html_to_pdf", fake_html_to_pdf):
            r = self.client.get(f"/comparativo.pdf?a={b}&b={a}")
        self.assertEqual((r.status_code, r.headers["content-type"]), (200, "application/pdf"))
        self.assertIn('filename="Comparativo-clinica-x-2026-09-01-a-2026-10-08.pdf"', r.headers["content-disposition"])

    def test_erros_explicam_e_nao_geram(self):
        a = self.analysis(raw_before())
        retro = self.analysis(raw_after(), kind="retroativa")
        with mock.patch.object(webapp, "html_to_pdf", fake_html_to_pdf) as gen:
            r = self.client.get(f"/comparativo.pdf?a={a}&b={retro}")
            self.assertEqual(r.status_code, 409)
            self.assertIn("análise real", r.text)
            self.assertEqual(self.client.get(f"/comparativo.pdf?a=998&b=999").status_code, 409)

    def test_pdf_de_uma_analise_do_historico(self):
        old = self.analysis(make_raw("2026-09-15T12:00:00+00:00"))
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"))
        with mock.patch.object(webapp, "html_to_pdf", fake_html_to_pdf):
            r = self.client.get(f"/relatorio.pdf?local=locations/1&analise={old}&modo=resumo")
        self.assertEqual(r.status_code, 200)
        self.assertIn('filename="Relatorio-Resumo-clinica-x-2026-09-15.pdf"', r.headers["content-disposition"])

    def test_botoes_no_historico_e_na_comparacao(self):
        a = self.analysis(raw_before())
        retro = self.analysis(raw_after("2026-09-20T12:00:00+00:00"), kind="retroativa")
        b = self.analysis(raw_after())
        html = self.client.get("/historico?local=locations/1").text
        self.assertIn('formaction="/comparativo.pdf"', html)
        self.assertIn(f'href="/relatorio.pdf?local=locations/1&amp;analise={a}"', html)
        self.assertIn(f'href="/relatorio.pdf?local=locations/1&amp;analise={b}&amp;modo=resumo"', html)
        self.assertNotIn(f"analise={retro}", html)  # retroativa nao tem PDF
        self.assertIn(f"#{a}", html)
        self.assertIn(f'href="/comparativo.pdf?a={a}&amp;b={b}"', self.client.get(f"/comparar?a={a}&b={b}").text)
        self.assertNotIn("/comparativo.pdf", self.client.get(f"/comparar?a={a}&b={retro}").text)


class CompareCliTest(TempStorage):
    def test_comparativo_e_relatorio_de_uma_analise(self):
        a, b = self.analysis(raw_before()), self.analysis(raw_after(errors={"localPosts": "x"}))
        out = io.StringIO()
        with mock.patch.object(coletar, "html_to_pdf", fake_html_to_pdf), redirect_stdout(out):
            coletar.cmd_comparativo(self.db, mock.Mock(a=a, b=b, saida=None))
            coletar.cmd_relatorio(self.db, mock.Mock(alvo="Clinica X", saida=None, resumo=False, analise=a))
        folder = os.path.join(self.tmp.name, "relatorios")
        self.assertTrue(os.path.isfile(os.path.join(folder, "Comparativo-clinica-x-2026-09-01-a-2026-10-08.pdf")))
        self.assertTrue(os.path.isfile(os.path.join(folder, "Relatorio-clinica-x-2026-09-01.pdf")))
        self.assertIn("ATENCAO", out.getvalue())

    def test_erro_sai_com_mensagem(self):
        a = self.analysis(raw_before())
        with self.assertRaises(SystemExit) as ctx:
            coletar.cmd_comparativo(self.db, mock.Mock(a=a, b=a, saida=None))
        self.assertIn("duas análises diferentes", str(ctx.exception))


@unittest.skipUnless(HAS_CHROME, "Chrome nao encontrado")
class ComparePdfTest(TempStorage):
    def test_pdf_de_verdade(self):
        from pypdf import PdfReader
        a = self.analysis(raw_before())
        self.analysis(raw_before("2026-09-20T12:00:00+00:00"))
        b = self.analysis(raw_after())
        out = os.path.join(self.tmp.name, "c.pdf")
        html_to_pdf(render.render_comparison_html(build_comparison_report(self.db, a, b)), out)
        reader = PdfReader(out)
        for page in reader.pages:
            w, h = (float(x) for x in page.mediabox[2:])
            self.assertAlmostEqual(w, 595.3, delta=1.5)
            self.assertAlmostEqual(h, 841.9, delta=1.5)
        n = len(reader.pages)
        self.assertGreaterEqual(n, 4)
        for i, page in enumerate(reader.pages, 1):
            self.assertIn(f"Página {i} de {n}", page.extract_text())
        text = "\n".join(p.extract_text() for p in reader.pages).lower()
        for needle in ("antes e depois", "números do perfil", "o que mudou nos itens", "melhoraram",
                       "evolução da nota", "comparativo de 01/09/2026 a 08/10/2026"):
            self.assertIn(needle, text)
        self.assertNotIn(REVIEW_TEXT, text)


if __name__ == "__main__":
    unittest.main()
