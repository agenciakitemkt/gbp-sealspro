"""Tela /simulador: a partir da Completa (?local=) e da Pre (?pre=)."""

import re

from starlette.testclient import TestClient

from tests.test_history import TempStorage
from tests.test_report import make_raw
from tests.test_report_pre import Base as PreBase
from web import app as webapp


def client():
    return TestClient(webapp.app, base_url="http://127.0.0.1:8000")


class SimuladorCompletaTest(TempStorage):
    def test_abre_pela_ultima_analise_real(self):
        self.analysis(make_raw())
        r = client().get("/simulador?local=locations/1")
        self.assertEqual(r.status_code, 200)
        for needle in ("Simulador de avaliações", "Nota de hoje", "Risco de queda", "Faixas de nota",
                       'href="/?local=locations/1"'):
            self.assertIn(needle, r.text)

    def test_sem_analise_real(self):
        self.analysis(make_raw(), kind="retroativa")
        self.assertEqual(client().get("/simulador?local=locations/1").status_code, 404)
        self.assertEqual(client().get("/simulador").status_code, 404)


class SimuladorPreTest(PreBase):
    def save_dist(self, dist):
        return self.save(reviews__starDistribution=dist, reviews__count=sum(dist), location__starDistribution=dist,
                         location__reviewCount=sum(dist))

    def test_meta_ritmo_e_periodo(self):
        aid = self.save_dist([2, 0, 0, 0, 1])  # 3,7
        h = client().get(f"/simulador?pre={aid}&meta=47&ritmo=2&periodo=semana").text
        self.assertIn("nota no Google 3,7", h)
        self.assertRegex(h, r'<option value="47" selected>4,7 \(Excelente\)</option>')
        self.assertRegex(h, r'class="sim-big">9</p>')
        self.assertIn("cerca de <strong>1 mês</strong> (35 dias)", h)
        self.assertIn(f'href="/pre?id={aid}"', h)
        self.assertNotIn("confirm(", h)

    def test_valores_invalidos_nao_quebram(self):
        aid = self.save_dist([2, 0, 0, 0, 1])
        r = client().get(f"/simulador?pre={aid}&meta=3&ritmo=0&periodo=<script>")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("<script>", r.text)

    def test_sem_avaliacoes_explica(self):
        aid = self.save_dist([0, 0, 0, 0, 0])
        r = client().get(f"/simulador?pre={aid}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ainda não tem avaliações", r.text)

    def test_nome_capturado_sai_escapado(self):
        aid = self.save(location__name="<script>alert(1)</script>")
        self.assertNotIn("<script>alert(1)", client().get(f"/simulador?pre={aid}").text)

    def test_pre_inexistente(self):
        self.assertEqual(client().get("/simulador?pre=999").status_code, 404)

    def test_ritmos_prontos_mantem_meta_e_periodo(self):
        aid = self.save_dist([2, 0, 0, 0, 1])
        h = client().get(f"/simulador?pre={aid}&meta=43&periodo=mes").text
        links = re.findall(r'href="(/simulador\?[^"]+)"', h)
        self.assertIn(f"/simulador?pre={aid}&amp;meta=43&amp;ritmo=15&amp;periodo=mes", links)
