import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from starlette.testclient import TestClient

import serve
import storage
from scoring import analyze
from scoring.base import overall_status
from service import AnalysisError
from web import app as webapp
from web import format as fmt
from tests.scoring.helpers import referencia

HEADERS = {"hx-request": "true"}


class FormatTest(unittest.TestCase):
    def test_idade(self):
        now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
        ago = lambda **kw: (now - timedelta(**kw)).isoformat()  # noqa: E731
        self.assertEqual(fmt.humanize_age(ago(seconds=20), now), "agora há pouco")
        self.assertEqual(fmt.humanize_age(ago(minutes=1), now), "há 1 minuto")
        self.assertEqual(fmt.humanize_age(ago(hours=5), now), "há 5 horas")
        self.assertEqual(fmt.humanize_age(ago(days=1, hours=2), now), "há 1 dia")
        self.assertEqual(fmt.humanize_age(ago(days=9), now), "há 9 dias")

    def test_marcador_em_tres_faixas_iguais(self):
        self.assertEqual(fmt.band_position(0), 0)
        self.assertAlmostEqual(fmt.band_position(49), 100 / 3 * 0.98)
        self.assertAlmostEqual(fmt.band_position(50), 100 / 3)
        self.assertLess(fmt.band_position(99), 100)
        self.assertEqual(fmt.band_position(100), 100)

    def test_horarios_agrupados(self):
        hours = {d: [["07:00", "16:00"]] for d in ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY")}
        self.assertEqual(fmt.format_hours(hours), [("Seg a Sex", "07:00–16:00"), ("Sáb e Dom", "Fechado")])

    def test_mensagem_com_decimal_em_virgula(self):
        msg = {"template": "Média {current} de {total}", "vars": {"current": 4.5, "total": 3}}
        self.assertEqual(fmt.render_message(msg), "Média 4,5 de 3")

    def test_faixas_do_medidor_geral(self):  # observado: 95 = Bom, 75 = Razoável
        self.assertEqual([overall_status(s) for s in (95, 81, 80, 75, 60, 59, 0)],
                         ["good", "good", "fair", "fair", "fair", "bad", "bad"])
        self.assertEqual(overall_status(None), "unavailable")


class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patches = [mock.patch.object(storage, "DATA", self.tmp.name),
                   mock.patch.object(storage, "DB", os.path.join(self.tmp.name, "t.db"))]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.db = storage.connect()
        self.addCleanup(self.db.close)
        storage.upsert_location(self.db, "locations/1", "accounts/1", "Clinica Um", "Belo Horizonte", "Conta Teste")
        storage.upsert_location(self.db, "locations/2", "accounts/1", "Clinica Dois", "Ouro Preto", "Conta Teste")
        storage.upsert_location(self.db, "locations/9", "accounts/1", "Ex-cliente Inativo", "Betim", "Conta Teste")
        storage.set_active(self.db, "locations/9", False)
        self.db.commit()
        self.client = TestClient(webapp.app, base_url="http://127.0.0.1:8000")

    def save(self, loc="locations/1", profile=None, when=None):
        result = analyze(profile or referencia())
        if when:
            result["analyzedAt"] = when
        storage.save_analysis(self.db, loc, result, "/tmp/raw.json")
        return result

    # ---- leitura ----
    def test_seletor_mostra_so_locais_ativos(self):
        html = self.client.get("/").text
        self.assertIn("Clinica Um", html)
        self.assertIn("Clinica Dois", html)
        self.assertNotIn("Ex-cliente Inativo", html)

    def test_local_inativo_na_url_cai_no_padrao(self):
        html = self.client.get("/?local=locations/9").text
        self.assertNotIn("Ex-cliente Inativo", html)

    def test_sem_analise_mostra_convite(self):
        html = self.client.get("/?local=locations/1").text
        self.assertIn("ainda não foi analisado", html)
        self.assertIn("Ainda sem análise guardada", html)

    def test_sem_locais_ativos(self):
        for loc in ("locations/1", "locations/2"):
            storage.set_active(self.db, loc, False)
        self.db.commit()
        self.assertIn("Nenhum local ativo", self.client.get("/").text)

    def test_abre_com_a_ultima_analise_guardada(self):
        old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        self.save(when=old)
        html = self.client.get("/?local=locations/1").text
        self.assertIn("Última atualização", html)
        self.assertIn("há 3 dias", html)
        self.assertIn("Conta: Conta Teste", html)

    def test_tela_da_referencia_tem_medidor_contadores_e_itens(self):
        self.save()
        html = self.client.get("/?local=locations/1").text
        self.assertIn('aria-label="Nota geral 95 de 100, faixa Bom"', html)
        self.assertEqual(html.count('class="item st-'), 21)
        self.assertLess(html.index("Mídias publicadas por clientes"), html.index("Número de telefone"))  # piores primeiro
        for label in ("Fraco", "Razoável", "Bom"):
            self.assertIn(f'<span class="counter-name">{label}</span>', html)
        self.assertIn("Ver no Maps", html)
        self.assertIn("Ver na Pesquisa", html)
        for star in range(5, 0, -1):
            self.assertIn(f"{star} ★", html)

    def test_status_nunca_so_por_cor(self):
        self.save()
        html = self.client.get("/?local=locations/1").text
        self.assertIn('<svg class="icon"', html)  # ícone
        self.assertRegex(html, r'(?s)class="badge st-fair">\s*<svg.*?</svg>Razoável')  # texto junto do ícone

    def test_itens_indisponiveis_vao_ao_final_em_estilo_neutro(self):
        p = referencia()
        p["collectionErrors"] = {"localPosts": "HTTP 500"}
        self.save(profile=p)
        html = self.client.get("/?local=locations/1").text
        self.assertIn("Fora da nota nesta análise", html)
        self.assertIn('class="item st-unavailable"', html)
        self.assertLess(html.index("Nome do negócio"), html.index("Data da última postagem"))
        self.assertTrue(html.rstrip().endswith("</html>"))
        last_item = html.rindex('class="item st-')
        self.assertTrue(html[last_item:].startswith('class="item st-unavailable"'))
        self.assertIn("sem avaliação porque a coleta falhou", html)
        self.assertIn("Não foi possível coletar este dado.", html)
        self.assertNotIn("localPosts", html)  # nome interno da secao nao aparece

    def test_analise_guardada_com_o_texto_antigo_aparece_com_o_texto_novo(self):
        p = referencia()
        p["collectionErrors"] = {"media": "HTTP 500"}
        result = analyze(p)
        for item in result["items"]:  # simula uma analise guardada antes da Fase 5a
            if item["status"] == "unavailable":
                item["message"]["template"] = "Não foi possível avaliar este item: os dados de {sections} não puderam ser coletados."
        storage.save_analysis(self.db, "locations/1", result, "/tmp/raw.json")
        html = self.client.get("/?local=locations/1").text
        self.assertIn("Não foi possível coletar este dado.", html)
        self.assertNotIn("dados de media", html)
        self.assertNotIn("Não foi possível avaliar este item", html)

    def test_item_que_nao_se_aplica_fica_ao_final_com_rotulo_proprio(self):
        p = referencia()
        p["location"]["servicesEditable"] = False
        self.save(profile=p)
        html = self.client.get("/?local=locations/1").text
        self.assertIn("Não se aplica", html)
        self.assertIn('class="item st-not_applicable"', html)
        self.assertIn("Fora da nota nesta análise", html)
        self.assertNotIn("sem avaliação porque a coleta falhou", html)  # nao e falha de coleta
        self.assertTrue(html[html.rindex('class="item st-'):].startswith('class="item st-not_applicable"'))

    def test_historico_mantem_a_antiga_e_mostra_a_mais_recente(self):
        first = referencia()
        first["location"]["rating"] = 4.0
        self.save(profile=first, when="2026-10-01T00:00:00+00:00")
        self.save(when="2026-10-05T00:00:00+00:00")
        n = self.db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        self.assertEqual(n, 2)
        self.assertEqual(storage.latest_analysis(self.db, "locations/1")["analyzed_at"], "2026-10-05T00:00:00+00:00")

    # ---- Analisar ----
    def fake_run(self, profile=None):
        def run(db, location):
            raw_path = "/tmp/raw.json"
            storage.save_analysis(db, location["id"], analyze(profile or referencia()), raw_path)
        return run

    def test_analisar_via_htmx_salva_e_devolve_a_tela(self):
        with mock.patch.object(webapp, "run_analysis", self.fake_run()):
            r = self.client.post("/analisar?local=locations/1", headers=HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["HX-Push-Url"], "/?local=locations%2F1")
        self.assertIn("Nota geral 95 de 100", r.text)
        self.assertIsNotNone(storage.latest_analysis(self.db, "locations/1"))

    def test_analisar_sem_js_redireciona(self):
        with mock.patch.object(webapp, "run_analysis", self.fake_run()):
            r = self.client.post("/analisar?local=locations/1", follow_redirects=False)
        self.assertEqual(r.status_code, 303)

    def test_erro_na_coleta_aparece_na_tela_sem_apagar_a_analise_anterior(self):
        self.save()
        with mock.patch.object(webapp, "run_analysis", side_effect=AnalysisError("HTTP 403: sem permissão")):
            r = self.client.post("/analisar?local=locations/1", headers=HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertIn('role="alert"', r.text)
        self.assertIn("HTTP 403: sem permissão", r.text)
        self.assertIn("Nota geral 95 de 100", r.text)

    def test_analise_ja_em_andamento(self):
        webapp._analysis_lock.acquire()
        try:
            r = self.client.post("/analisar?local=locations/1", headers=HEADERS)
        finally:
            webapp._analysis_lock.release()
        self.assertIn("análise em andamento", r.text)

    def test_nao_analisa_local_inativo_nem_inexistente(self):
        for loc in ("locations/9", "locations/404"):
            self.assertEqual(self.client.post(f"/analisar?local={loc}", headers=HEADERS).status_code, 404)

    # ---- segurança local ----
    def test_recusa_host_que_nao_e_local(self):
        r = TestClient(webapp.app, base_url="http://evil.example").get("/")
        self.assertEqual(r.status_code, 400)

    def test_recusa_post_de_outro_site(self):
        with mock.patch.object(webapp, "run_analysis", self.fake_run()) as run:
            r = self.client.post("/analisar?local=locations/1", headers={"origin": "https://evil.example"})
            r2 = self.client.post("/analisar?local=locations/1", headers={"sec-fetch-site": "cross-site"})
        self.assertEqual((r.status_code, r2.status_code), (403, 403))

    def test_aceita_post_da_propria_tela(self):
        with mock.patch.object(webapp, "run_analysis", self.fake_run()):
            r = self.client.post("/analisar?local=locations/1",
                                 headers={**HEADERS, "origin": "http://127.0.0.1:8000", "sec-fetch-site": "same-origin"})
        self.assertEqual(r.status_code, 200)

    def test_servidor_escuta_so_em_loopback(self):
        self.assertEqual(serve.HOST, "127.0.0.1")
        with open(serve.__file__, encoding="utf-8") as f:
            self.assertNotIn("--host", f.read())  # o endereço não é configurável

    def test_html_escapa_conteudo_do_perfil(self):
        p = referencia()
        p["location"]["name"] = "<script>alert(1)</script>"
        self.save(profile=p)
        self.assertNotIn("<script>alert(1)</script>", self.client.get("/?local=locations/1").text)


if __name__ == "__main__":
    unittest.main()
