import io
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import coletar
import storage
from report import build, render, texts
from report.build import ReportError, build_report
from report.pdf import PdfError, find_chrome, html_to_pdf
from scoring import analyze, version
from collector.normalize import normalize
from starlette.testclient import TestClient
from tests.test_history import TempStorage
from tests.test_normalize import raw as raw_fixture
from web import app as webapp

HAS_CHROME = find_chrome() is not None
REVIEW_TEXT = "texto privado do cliente que nunca pode aparecer"


def make_raw(collected="2026-10-08T12:00:00+00:00", services=True, **extra):
    """Bruto de teste: uma avaliacao com texto privado (que nunca pode aparecer) e, por padrao, tudo coletado.
    services=False simula um tipo de negocio que nao aceita lista de servicos (item 'nao se aplica')."""
    raw = raw_fixture(collectedAt=collected)
    raw["reviews"] = raw["reviews"] + [{"starRating": "FIVE", "comment": REVIEW_TEXT, "createTime": "2026-10-07T00:00:00Z",
                                        "reviewReply": {"comment": "resposta"}}]
    raw["reviewsSummary"] = {"averageRating": 4.7, "totalReviewCount": len(raw["reviews"])}  # lista completa
    if services:
        raw["info"] = {**raw["info"], "metadata": {**raw["info"]["metadata"], "canModifyServiceList": True}}
    raw.update(extra)
    return raw


# ---------------------------------------------------------------------------
# Textos
# ---------------------------------------------------------------------------

SAMPLES = {  # item -> (variaveis em bom estado, variaveis abaixo do ideal)
    "phone": ({"current": "(31) 99999-0000"}, {}), "website": ({"current": "https://exemplo.com.br/"}, {}),
    "hours": ({"current": 5}, {}), "special_hours": ({"current": 2, "year": 2026}, {"current": 0, "year": 2026}),
    "description": ({"current": 585, "recommended": 50}, {"current": 32, "recommended": 50}),
    "videos": ({"current": 3, "recommended": 3}, {"current": 2, "recommended": 3}), "logo": ({}, {}), "cover": ({}, {}),
    "owner_media": ({"current": 8, "recommended": 3}, {"current": 2, "recommended": 3}),
    "total_media": ({"current": 9, "recommended": 3}, {"current": 2, "recommended": 3}),
    "customer_media": ({"current": 3, "recommended": 3}, {"current": 1, "recommended": 3}),
    "reviews_count": ({"current": 21, "recommended": 3}, {"current": 2, "recommended": 3}),
    "reviews_average": ({"current": 4.8}, {"current": 3.9, "recommended": 4.5}),
    "reviews_unanswered": ({"current": 0, "total": 22}, {"current": 3, "total": 22}),
    "reviews_no_comment": ({"current": 6, "total": 22, "percent": 27}, {"current": 11, "total": 25, "percent": 44}),
    "services": ({"current": 4}, {}), "founding_date": ({"current": "2020-03-15"}, {}),
    "business_name": ({"current": 34, "recommended": 98}, {"current": 112, "recommended": 98}),
    "reviews_trend": ({"trend": "up", "days": 90, "recent": 4.9, "historical": 4.6},
                      {"trend": "down", "days": 90, "recent": 4.1, "historical": 4.7}),
    "last_post": ({"current": 3, "recommended": 30}, {"current": 43, "recommended": 30}),
    "last_owner_media": ({"current": 8, "recommended": 59}, {"current": 86, "recommended": 59}),
}
SPECIAL = [  # variantes sem dado (status, item, variaveis)
    ("fair", "reviews_average", {"current": 0.0}), ("good", "reviews_unanswered", {"current": 0, "total": 0}),
    ("good", "reviews_unanswered", {"current": 0, "total": 1}), ("bad", "reviews_no_comment", {"current": 0, "total": 0, "percent": 0}),
    ("good", "reviews_trend", {"trend": "stable", "days": 90}),
    ("good", "reviews_trend", {"trend": "stable", "days": 90, "recent": 4.8, "historical": 4.8, "delta": 0.0}),
    ("bad", "last_post", {"current": None, "recommended": 30}), ("bad", "last_owner_media", {"current": None, "recommended": 59}),
    ("good", "last_post", {"current": 1, "recommended": 30}), ("bad", "reviews_count", {"current": 1, "recommended": 3}),
    ("bad", "reviews_unanswered", {"current": 1, "total": 25}),
]
FORBIDDEN_IN_ADVICE = ("garant", "prazo", "em até", "semanas", "meses", "aumentará", "aumentarão", "vai aumentar",
                       "dobr", "triplic", "ranking", "primeiro lugar", "resultado", "vai ", "irá ", "conseguirá")
JARGON = ("API", "JSON", "hash", "score", "motor", "legacy", "config", "Fase", "retroativ", "readMask", "engine", "None", "nan")


class TextsTest(unittest.TestCase):
    def all_texts(self):
        for item_id, (good, low) in SAMPLES.items():
            yield "good", item_id, good
            yield "fair", item_id, low
        yield from SPECIAL

    def test_os_21_itens_tem_titulo_e_textos_para_os_dois_estados(self):
        self.assertEqual(len(texts.TITLES), 21)
        self.assertEqual(set(texts.TITLES), set(texts.GOOD) | set())
        self.assertEqual(set(texts.GOOD), set(texts.LOW))
        self.assertEqual(set(SAMPLES), set(texts.TITLES))
        self.assertEqual(len(set(texts.TITLES.values())), 21)  # titulos distintos

    def test_todos_os_itens_do_motor_tem_texto(self):
        from scoring.items import ITEMS
        self.assertEqual({i.id for i in ITEMS}, set(texts.TITLES))

    def test_nenhum_texto_fica_com_variavel_sobrando_ou_vazio(self):
        for status, item_id, v in self.all_texts():
            title, situation, advice, kind = texts.describe(item_id, status, v)
            for text in (title, situation, advice):
                self.assertTrue(text.strip(), (item_id, status))
                self.assertNotRegex(text, r"[{}]", (item_id, status, text))
            self.assertEqual(kind, "manter" if status == "good" else "fazer")

    def test_orientacao_nao_promete_prazo_nem_resultado(self):
        for status, item_id, v in self.all_texts():
            advice = texts.describe(item_id, status, v)[2].lower()
            for word in FORBIDDEN_IN_ADVICE:
                self.assertNotIn(word, advice, (item_id, word))

    def test_sem_jargao_tecnico(self):
        for status, item_id, v in self.all_texts():
            for text in texts.describe(item_id, status, v):
                for word in JARGON:
                    self.assertIsNone(re.search(rf"\b{re.escape(word)}\b", text), (item_id, word, text))

    def test_numeros_aparecem_na_situacao(self):
        self.assertIn("2 de 3 vídeos", texts.describe("videos", "fair", {"current": 2, "recommended": 3})[1])
        self.assertIn("4,8 estrelas", texts.describe("reviews_average", "good", {"current": 4.8})[1])
        self.assertIn("15/03/2020", texts.describe("founding_date", "good", {"current": "2020-03-15"})[1])
        self.assertIn("43 dias", texts.describe("last_post", "bad", {"current": 43, "recommended": 30})[1])

    def test_ultima_foto_ou_video_fala_em_cerca_de_dois_meses_e_a_postagem_continua_em_dias(self):
        photo = texts.describe("last_owner_media", "fair", {"current": 86, "recommended": 59})[1]
        self.assertEqual(photo, "A última foto ou vídeo da empresa foi publicado há 86 dias; o ideal é renovar a cada cerca de dois meses.")
        self.assertNotIn("59", photo)
        post = texts.describe("last_post", "bad", {"current": 43, "recommended": 30})[1]
        self.assertIn("pelo menos a cada 30 dias", post)

    def test_singular_e_plural(self):
        self.assertIn("1 avaliação ainda está sem resposta", texts.describe("reviews_unanswered", "bad", {"current": 1, "total": 25})[1])
        self.assertIn("3 avaliações ainda estão sem resposta", texts.describe("reviews_unanswered", "bad", {"current": 3, "total": 25})[1])
        self.assertIn("há 1 dia.", texts.describe("last_post", "good", {"current": 1, "recommended": 30})[1])

    def test_frases_da_nota_geral(self):
        a, b = texts.overall_sentences("good", {"good": 19, "fair": 2, "bad": 0})
        self.assertIn("ótimo estado", a)
        self.assertIn("19 estão em bom estado", b)
        self.assertIn("precisa de atenção", texts.overall_sentences("bad", {"good": 1, "fair": 1, "bad": 9})[0])
        self.assertIn("razoável", texts.overall_sentences("fair", {"good": 5, "fair": 5, "bad": 0})[0])


# ---------------------------------------------------------------------------
# Montagem dos dados
# ---------------------------------------------------------------------------

class BuildTest(TempStorage):
    def test_usa_a_ultima_analise_real_e_ignora_retroativas(self):
        real = self.analysis(make_raw("2026-10-01T12:00:00+00:00"), kind="real")
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"), kind="retroativa")  # mais nova, mas retroativa
        report = build_report(self.db, "locations/1")
        self.assertEqual(report["analysis_id"], real)
        self.assertEqual(report["date"], "01/10/2026")

    def test_so_retroativas_nao_gera_relatorio(self):
        self.analysis(make_raw(), kind="retroativa")
        with self.assertRaisesRegex(ReportError, "ainda não tem uma análise real"):
            build_report(self.db, "locations/1")

    def test_sem_analise_nenhuma(self):
        with self.assertRaises(ReportError):
            build_report(self.db, "locations/2")

    def test_itens_do_pior_para_o_melhor_com_titulos_do_cliente(self):
        self.analysis(make_raw())
        report = build_report(self.db, "locations/1")
        self.assertEqual([g["status"] for g in report["groups"]], sorted((g["status"] for g in report["groups"]),
                                                                           key=["bad", "fair", "good"].index))
        titles = [i["title"] for g in report["groups"] for i in g["items"]]
        self.assertTrue(set(titles) <= set(texts.TITLES.values()))
        self.assertNotIn("Mídia: vídeos", titles)  # titulo tecnico do motor nao aparece

    def test_contadores_nota_e_frases(self):
        self.analysis(make_raw())
        r = build_report(self.db, "locations/1")
        o = analyze(normalize({**make_raw(), "location": "locations/1"}))["overall"]
        self.assertEqual((r["overall"]["score"], r["counts"]), (o["score"], {"good": o["good"], "fair": o["fair"], "bad": o["bad"]}))
        self.assertTrue(r["sentence_1"] and "itens avaliados" in r["sentence_2"])

    def test_nao_avaliados_ficam_numa_lista_a_parte_e_fora_dos_grupos(self):
        self.analysis(make_raw(services=False, errors={"localPosts": "HTTP 500"}))  # postagens indisponiveis; servicos nao se aplica
        r = build_report(self.db, "locations/1")
        reasons = {s["title"]: s["reason"] for s in r["skipped"]}
        self.assertEqual(reasons["Última postagem"], "Não foi possível coletar este dado.")
        self.assertEqual(reasons["Serviços cadastrados"], "Não se aplica ao tipo de negócio deste perfil.")
        in_groups = {i["title"] for g in r["groups"] for i in g["items"]}
        self.assertFalse(in_groups & set(reasons))
        self.assertEqual(sum(len(g["items"]) for g in r["groups"]), 21 - 2)

    def test_aviso_de_itens_nao_avaliados(self):
        self.analysis(make_raw(errors={"localPosts": "x", "mediaCustomers": "x"}))
        warnings = build_report(self.db, "locations/1")["warnings"]
        self.assertTrue(any("não puderam ser avaliado" in w for w in warnings), warnings)

    def test_aviso_de_versao_anterior(self):
        self.analysis(make_raw(), engine_version="0", config_hash="z" * 64)
        self.assertTrue(any("versão anterior" in w for w in build_report(self.db, "locations/1")["warnings"]))
        self.assertTrue(build.is_current_version({"engine_version": version.ENGINE_VERSION, "config_hash": version.config_hash()}))

    def test_sem_avisos_quando_esta_tudo_certo(self):
        self.analysis(make_raw())
        r = build_report(self.db, "locations/1")
        self.assertEqual((r["warnings"], len(r["skipped"])), ([], 0))

    # ---- evolucao ----
    def test_evolucao_so_com_duas_ou_mais_reais_da_versao_atual(self):
        self.analysis(make_raw("2026-10-01T12:00:00+00:00"))
        self.assertIsNone(build_report(self.db, "locations/1")["evolution"])  # 1 so
        self.analysis(make_raw("2026-10-05T12:00:00+00:00"))
        evo = build_report(self.db, "locations/1")["evolution"]
        self.assertEqual((evo["count"], len(evo["chart"]["points"])), (2, 2))
        self.assertEqual(evo["chart"]["markers"], [])

    def test_evolucao_ignora_retroativas(self):
        self.analysis(make_raw("2026-10-01T12:00:00+00:00"), kind="real")
        self.analysis(make_raw("2026-10-02T12:00:00+00:00"), kind="retroativa")
        self.analysis(make_raw("2026-10-03T12:00:00+00:00"), kind="retroativa")
        self.assertIsNone(build_report(self.db, "locations/1")["evolution"])

    def test_evolucao_ignora_outras_versoes_do_motor_e_do_config(self):
        self.analysis(make_raw("2026-10-01T12:00:00+00:00"), engine_version="0")
        self.analysis(make_raw("2026-10-02T12:00:00+00:00"), config_hash="y" * 64)
        self.analysis(make_raw("2026-10-03T12:00:00+00:00"))
        self.assertIsNone(build_report(self.db, "locations/1")["evolution"])  # so 1 da versao atual
        self.analysis(make_raw("2026-10-04T12:00:00+00:00"))
        self.assertEqual(build_report(self.db, "locations/1")["evolution"]["count"], 2)

    def test_frase_da_evolucao(self):
        self.analysis(make_raw("2026-10-01T12:00:00+00:00"))
        self.analysis(make_raw("2026-10-05T12:00:00+00:00"))
        self.assertIn("se manteve em", build_report(self.db, "locations/1")["evolution"]["sentence"])
        self.analysis(make_raw("2026-10-09T12:00:00+00:00"))
        self.analysis(make_raw("2026-10-10T12:00:00+00:00", media=[]))
        self.assertRegex(build_report(self.db, "locations/1")["evolution"]["sentence"], r"A nota geral (subiu|caiu) de")

    def test_evolucao_com_analises_so_no_mesmo_dia_e_omitida(self):
        for hour in (9, 12, 15):
            self.analysis(make_raw(f"2026-10-05T{hour:02d}:00:00+00:00"))
        self.assertIsNone(build_report(self.db, "locations/1")["evolution"])  # 3 analises, 1 data

    def test_evolucao_conta_datas_de_brasilia_e_nao_de_utc(self):
        # 02:30Z e 03:30Z do dia 06 em UTC: 23:30 de 05/10 e 00:30 de 06/10 em Brasilia = 2 datas diferentes
        self.analysis(make_raw("2026-10-06T02:30:00+00:00"))
        self.analysis(make_raw("2026-10-06T03:30:00+00:00"))
        evo = build_report(self.db, "locations/1")["evolution"]
        self.assertEqual(evo["count"], 2)
        self.assertIn("05/10/2026", evo["sentence"])
        self.assertIn("06/10/2026", evo["sentence"])

    def test_mesmo_dia_em_brasilia_mesmo_com_datas_utc_diferentes(self):
        # 20:00 do dia 05 em Brasilia = 23:00Z (05/10); 22:30 do dia 05 em Brasilia = 01:30Z (06/10)
        self.analysis(make_raw("2026-10-05T23:00:00+00:00"))
        self.analysis(make_raw("2026-10-06T01:30:00+00:00"))
        self.assertIsNone(build_report(self.db, "locations/1")["evolution"])

    def test_varias_no_mesmo_dia_mais_outra_data_entram_todas(self):
        self.analysis(make_raw("2026-10-05T12:00:00+00:00"))
        self.analysis(make_raw("2026-10-05T15:00:00+00:00"))
        self.analysis(make_raw("2026-10-07T12:00:00+00:00"))
        self.assertEqual(build_report(self.db, "locations/1")["evolution"]["count"], 3)

    def test_data_do_arquivo_e_a_de_brasilia_como_no_relatorio(self):
        self.analysis(make_raw("2026-10-09T02:47:00+00:00"))  # 23:47 de 08/10 em Brasilia
        r = build_report(self.db, "locations/1")
        self.assertEqual((r["date"], r["filename"]), ("08/10/2026", "Relatorio-clinica-x-2026-10-08.pdf"))

    def test_nome_do_arquivo(self):
        self.assertEqual(build.slug("DRA Maria Exemplo - Oftalmologista"), "dra-maria-exemplo-oftalmologista")
        self.assertEqual(build.slug("Clínica Ação & Cia"), "clinica-acao-cia")
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"))
        self.assertEqual(build_report(self.db, "locations/1")["filename"], "Relatorio-clinica-x-2026-10-08.pdf")


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

class RenderTest(TempStorage):
    def html(self, evolution=False, skipped=False, name=None):
        raw = make_raw("2026-10-01T12:00:00+00:00", errors={"localPosts": "x"} if skipped else {})
        if name:
            raw["info"] = {**raw["info"], "title": name}
        self.analysis(raw)
        if evolution:
            self.analysis({**raw, "collectedAt": "2026-10-05T12:00:00+00:00"})
        return render.render_html(build_report(self.db, "locations/1"))

    def test_secoes_do_relatorio(self):
        h = self.html(evolution=True, skipped=True)
        for needle in ("Relatório de desempenho do perfil no Google", "Resumo da análise", "Itens analisados",
                       "Evolução da nota", "O que fazer", "Preparado pela SealsPro",
                       "Critérios próprios da SealsPro", "Análise realizada em 05/10/2026"):  # a mais recente
            self.assertIn(needle, h)
        # problemas da analise (item nao coletado) ficam so na tela, nunca no PDF
        self.assertNotIn("Não avaliados nesta análise", h)
        self.assertNotIn("Não foi possível coletar", h)

    def test_secoes_opcionais_somem_quando_nao_ha_o_que_mostrar(self):
        h = self.html(evolution=False, skipped=False)
        self.assertNotIn("Evolução da nota", h)
        self.assertNotIn("Não avaliados nesta análise", h)

    def test_nota_so_na_geral_e_nunca_por_item(self):
        h = self.html()
        self.assertNotIn("/100", h)
        self.assertEqual(h.count("de 100"), 2)  # texto do medidor e o rotulo de acessibilidade, ambos da nota geral
        for block in re.findall(r'<article class="item.*?</article>', h, re.S):
            self.assertNotRegex(block, r"\b\d{1,3}\s*(/|de)\s*100\b")

    def test_texto_de_avaliacao_de_cliente_nunca_aparece(self):
        self.assertNotIn(REVIEW_TEXT, self.html())

    def test_nada_e_carregado_da_internet(self):
        h = self.html(evolution=True)
        self.assertEqual(re.findall(r'(?:src|href)="https?://', h), [])
        self.assertEqual(re.findall(r'url\(\s*["\']?https?://', h), [])
        for url in re.findall(r'url\("(file://[^"]+)"\)|src="(file://[^"]+)"', h):
            path = [u for u in url if u][0].replace("file://", "")
            self.assertTrue(os.path.isfile(path.replace("%20", " ")), path)

    def test_nome_do_local_e_escapado(self):
        self.assertNotIn("<script>alert(1)</script>", self.html(name="<script>alert(1)</script>"))

    def test_identidade_visual(self):
        h = self.html()
        for token in ("#0B0B0D", "#14B8A6", "#818CF8", "#F8FAFC", "Space Grotesk", "Inter"):
            self.assertIn(token, h)

    def test_status_com_icone_e_texto(self):
        h = self.html()
        self.assertRegex(h, r'(?s)class="badge">\s*<svg.*?</svg>(Bom|Razoável|Fraco)')

    def test_assets_existem_e_fontes_tem_licenca(self):
        for url in render.asset_urls().values():
            self.assertTrue(os.path.isfile(url.replace("file://", "").replace("%20", " ")), url)
        for lic in ("OFL-Inter.txt", "OFL-SpaceGrotesk.txt"):
            self.assertTrue(os.path.isfile(os.path.join(render.ASSETS, "fonts", lic)))


# ---------------------------------------------------------------------------
# PDF de verdade (Chrome local)
# ---------------------------------------------------------------------------

@unittest.skipUnless(HAS_CHROME, "Chrome nao encontrado")
class PdfTest(TempStorage):
    def make_pdf(self, evolution=True, skipped=True, name=None):
        raw = make_raw("2026-10-01T12:00:00+00:00", errors={"localPosts": "x"} if skipped else {})
        if name:
            raw["info"] = {**raw["info"], "title": name}
        self.analysis(raw)
        if evolution:
            self.analysis({**raw, "collectedAt": "2026-10-05T12:00:00+00:00"})
        out = os.path.join(self.tmp.name, "saida", "r.pdf")
        html_to_pdf(render.render_html(build_report(self.db, "locations/1")), out)
        return out

    def read(self, path):
        from pypdf import PdfReader
        return PdfReader(path)

    def text(self, reader):
        return "\n".join(p.extract_text() for p in reader.pages)

    def test_pdf_valido_em_a4(self):
        path = self.make_pdf()
        with open(path, "rb") as f:
            data = f.read()
        self.assertTrue(data.startswith(b"%PDF-") and b"%%EOF" in data[-64:])
        reader = self.read(path)
        self.assertGreaterEqual(len(reader.pages), 4)
        for page in reader.pages:
            w, h = (float(x) for x in page.mediabox[2:])
            self.assertAlmostEqual(w, 595.3, delta=1.5)  # A4 em pontos
            self.assertAlmostEqual(h, 841.9, delta=1.5)

    def test_fontes_embutidas_inter_e_space_grotesk(self):
        reader = self.read(self.make_pdf())
        fonts = {}
        for page in reader.pages:
            for obj in page["/Resources"].get("/Font", {}).values():
                font = obj.get_object()
                self.assertNotEqual(str(font.get("/Subtype")), "/Type3")
                descendant = font["/DescendantFonts"][0].get_object()
                descriptor = descendant["/FontDescriptor"].get_object()
                fonts[re.sub(r"^[A-Z]{6}\+", "", str(font["/BaseFont"]).lstrip("/"))] = "/FontFile2" in descriptor
        self.assertTrue(fonts and all(fonts.values()), fonts)  # todas embutidas
        self.assertTrue(any(n.startswith("Inter") for n in fonts), fonts)
        self.assertTrue(any(n.startswith("SpaceGrotesk") for n in fonts), fonts)

    def test_todas_as_secoes_no_texto_do_pdf(self):
        text = self.text(self.read(self.make_pdf()))
        for needle in ("Clinica X", "Resumo da análise", "Nota geral", "Itens analisados", "O que fazer",
                       "Como manter", "Evolução da nota",
                       "Critérios próprios da SealsPro", "SealsPro · Análise de 05/10/2026", "Preparado pela SealsPro"):
            self.assertIn(needle.lower(), text.lower(), needle)  # "O QUE FAZER" sai em caixa alta pelo CSS
        self.assertNotIn(REVIEW_TEXT, text)
        for problem in ("Não avaliados nesta análise", "Não foi possível coletar"):  # so na tela
            self.assertNotIn(problem.lower(), text.lower())

    def test_rodape_em_todas_as_paginas(self):
        reader = self.read(self.make_pdf())
        n = len(reader.pages)
        for i, page in enumerate(reader.pages, 1):
            t = page.extract_text()
            self.assertIn("SealsPro · Análise de", t)
            self.assertIn(f"Página {i} de {n}", t)

    def test_sem_evolucao_e_sem_nao_avaliados_as_secoes_somem(self):
        text = self.text(self.read(self.make_pdf(evolution=False, skipped=False)))
        self.assertNotIn("evolução da nota", text.lower())
        self.assertNotIn("não avaliados nesta análise", text.lower())
        self.assertIn("itens analisados", text.lower())

    def test_sem_texto_cortado_margens_externas_limpas_em_todas_as_paginas(self):
        import pypdfium2
        long_name = ("Clínica de Oftalmologia e Cirurgia Refrativa Avançada do Doutor Fulano de Tal Júnior e Associados "
                     "Supercalifragilisticoexpialidosoextraordinarioedemasiadamentelongo")
        path = self.make_pdf(name=long_name)
        pdf = pypdfium2.PdfDocument(path)
        for index in range(len(pdf)):
            image = pdf[index].render(scale=1).to_pil().convert("RGB")
            w, h = image.size
            m = 20  # ~7 mm de cada borda: so fundo (#0B0B0D), nunca texto ou elemento vazando
            for box in ((0, 0, m, h), (w - m, 0, w, h), (0, 0, w, m)):
                lo, hi = zip(*image.crop(box).getextrema())
                self.assertLessEqual(max(hi), 14, f"pagina {index + 1} tem conteudo na borda {box}")
                self.assertGreaterEqual(min(lo), 6, f"pagina {index + 1} sem fundo na borda {box}")
        self.assertIn("Supercalifragilistico", self.text(self.read(path)).replace("\n", ""))

    def test_paginas_nao_ficam_vazias(self):
        import pypdfium2
        pdf = pypdfium2.PdfDocument(self.make_pdf())
        for index in range(len(pdf)):
            image = pdf[index].render(scale=0.5).to_pil().convert("L")
            self.assertGreater(image.getextrema()[1], 60, f"pagina {index + 1} sem conteudo visivel")

    def test_gerador_cria_a_pasta_de_destino(self):
        self.assertTrue(os.path.isfile(self.make_pdf()))


class PdfGeneratorTest(unittest.TestCase):
    def test_sem_chrome_da_erro_claro(self):
        with mock.patch("report.pdf.find_chrome", return_value=None):
            with self.assertRaisesRegex(PdfError, "Chrome não foi encontrado"):
                html_to_pdf("<p>x</p>", os.path.join(tempfile.gettempdir(), "nao-sera-criado.pdf"))

    def test_variavel_gbp_chrome_tem_prioridade(self):
        with tempfile.NamedTemporaryFile() as f:
            with mock.patch.dict(os.environ, {"GBP_CHROME": f.name}):
                self.assertEqual(find_chrome(), f.name)

    def test_chrome_que_nao_gera_arquivo_vira_erro(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("report.pdf.find_chrome", return_value="/usr/bin/true"):
            with self.assertRaisesRegex(PdfError, "não gerou"):
                html_to_pdf("<p>x</p>", os.path.join(tmp, "x.pdf"))


# ---------------------------------------------------------------------------
# Rotas e linha de comando
# ---------------------------------------------------------------------------

FAKE_PDF = b"%PDF-1.4\n" + b"0" * 200 + b"\n%%EOF\n"


def fake_html_to_pdf(html, out_path, timeout=90):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(FAKE_PDF)
    return out_path


class RoutesTest(TempStorage):
    def setUp(self):
        super().setUp()
        self.client = TestClient(webapp.app, base_url="http://127.0.0.1:8000")


    def test_baixar_pdf_devolve_o_arquivo_com_nome_de_download(self):
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"))
        with mock.patch.object(webapp, "html_to_pdf", fake_html_to_pdf):
            r = self.client.get("/relatorio.pdf?local=locations/1")
        self.assertEqual((r.status_code, r.headers["content-type"]), (200, "application/pdf"))
        self.assertIn('attachment; filename="Relatorio-clinica-x-2026-10-08.pdf"', r.headers["content-disposition"])
        self.assertTrue(r.content.startswith(b"%PDF-"))

    def test_sem_analise_real_explica_e_nao_gera(self):
        self.analysis(make_raw(), kind="retroativa")
        with mock.patch.object(webapp, "html_to_pdf", fake_html_to_pdf) as gen:
            r = self.client.get("/relatorio.pdf?local=locations/1")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ainda não tem uma análise real", r.text)
        self.assertIn("Voltar à análise", r.text)

    def test_local_inativo_ou_inexistente(self):
        storage.set_active(self.db, "locations/2", False)
        self.db.commit()
        for loc in ("locations/2", "locations/404"):
            self.assertEqual(self.client.get(f"/relatorio.pdf?local={loc}").status_code, 404)

    def test_falha_do_chrome_mostra_mensagem(self):
        self.analysis(make_raw())
        with mock.patch.object(webapp, "html_to_pdf", side_effect=PdfError("O Chrome não foi encontrado.")):
            r = self.client.get("/relatorio.pdf?local=locations/1")
        self.assertEqual(r.status_code, 500)
        self.assertIn("Não foi possível gerar o PDF", r.text)

    def test_um_pdf_por_vez(self):
        self.analysis(make_raw())
        webapp._report_lock.acquire()
        try:
            r = self.client.get("/relatorio.pdf?local=locations/1")
        finally:
            webapp._report_lock.release()
        self.assertEqual(r.status_code, 409)
        self.assertIn("sendo gerado", r.text)

    def test_botao_baixar_pdf_so_aparece_com_analise_real(self):
        self.assertNotIn("Baixar PDF", self.client.get("/?local=locations/1").text)
        self.analysis(make_raw(), kind="retroativa")
        self.assertNotIn("Baixar PDF", self.client.get("/?local=locations/1").text)
        self.analysis(make_raw())
        html = self.client.get("/?local=locations/1").text
        self.assertIn('href="/relatorio.pdf?local=locations/1"', html)
        self.assertIn("Baixar PDF", html)
        self.assertIn('href="/relatorio.pdf?local=locations/1&amp;modo=resumo"', html)
        self.assertIn('href="/simulador?local=locations/1"', html)
        self.assertNotIn("confirm(", html)  # o PDF sai direto, sem pop-up
        self.assertNotIn("versão anterior dos critérios", html)

    def test_problemas_aparecem_so_na_tela_sem_popup(self):
        self.analysis(make_raw(errors={"localPosts": "HTTP 500"}), engine_version="0", config_hash="k" * 64)
        html = self.client.get("/?local=locations/1").text
        self.assertNotIn("confirm(", html)
        self.assertIn("versão anterior dos critérios", html)
        self.assertIn("1 item ficou sem avaliação", html)

    def test_pdf_resumido_pela_rota(self):
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"))
        with mock.patch.object(webapp, "html_to_pdf", fake_html_to_pdf):
            r = self.client.get("/relatorio.pdf?local=locations/1&modo=resumo")
        self.assertEqual(r.status_code, 200)
        self.assertIn('filename="Relatorio-Resumo-clinica-x-2026-10-08.pdf"', r.headers["content-disposition"])

    def test_seguranca_local_continua(self):
        self.assertEqual(TestClient(webapp.app, base_url="http://evil.example").get("/relatorio.pdf?local=x").status_code, 400)

    @unittest.skipUnless(HAS_CHROME, "Chrome nao encontrado")
    def test_rota_gera_pdf_de_verdade(self):
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"))
        r = self.client.get("/relatorio.pdf?local=locations/1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF-") and len(r.content) > 20000)


class CliTest(TempStorage):
    def run_cli(self, alvo="Clinica X", saida=None):
        args = mock.Mock(alvo=alvo, saida=saida, resumo=False, analise=None)
        out = io.StringIO()
        with redirect_stdout(out):
            coletar.cmd_relatorio(self.db, args)
        return out.getvalue()

    def test_gera_na_pasta_data_relatorios_por_padrao(self):
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"))
        with mock.patch.object(coletar, "html_to_pdf", fake_html_to_pdf):
            out = self.run_cli()
        expected = os.path.join(self.tmp.name, "relatorios", "Relatorio-clinica-x-2026-10-08.pdf")
        self.assertIn(f"Relatorio gerado: {expected}", out)
        self.assertTrue(os.path.isfile(expected))

    def test_pasta_de_saida_escolhida_e_avisos(self):
        self.analysis(make_raw(errors={"localPosts": "x"}))
        with tempfile.TemporaryDirectory() as dest, mock.patch.object(coletar, "html_to_pdf", fake_html_to_pdf):
            out = self.run_cli(saida=dest)
            self.assertTrue(os.path.isfile(os.path.join(dest, "Relatorio-clinica-x-2026-10-08.pdf")))
        self.assertIn("ATENCAO", out)

    def test_sem_analise_real_sai_com_mensagem(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli()
        self.assertIn("ainda não tem uma análise real", str(ctx.exception))

    def test_falha_do_chrome_sai_com_mensagem(self):
        self.analysis(make_raw())
        with mock.patch.object(coletar, "html_to_pdf", side_effect=PdfError("sem Chrome")):
            with self.assertRaises(SystemExit) as ctx:
                self.run_cli()
        self.assertIn("sem Chrome", str(ctx.exception))

    @unittest.skipUnless(HAS_CHROME, "Chrome nao encontrado")
    def test_gera_pdf_de_verdade(self):
        self.analysis(make_raw("2026-10-08T12:00:00+00:00"))
        self.run_cli()
        path = os.path.join(self.tmp.name, "relatorios", "Relatorio-clinica-x-2026-10-08.pdf")
        with open(path, "rb") as f:
            self.assertTrue(f.read(5) == b"%PDF-")


if __name__ == "__main__":
    unittest.main()
