"""Busca de Leads (CLAUDE.md, secao 18): regiao, grade, leitura de uma pagina, qualidade, fluxo no app, notas,
favoritos, planilha e seguranca. Respostas da busca montadas aqui no formato da fonte D (sem dados reais)."""

import csv
import io
import json
import os
import tempfile
import unittest
from contextlib import closing
from unittest import mock

from starlette.testclient import TestClient

import storage
from leads import config, plan, reader, region, service
from leads.quality import quality
from web import app as webapp
from web import pre as pre_web

EXT_ID = "abcdefghijklmnopabcdefghijklmnop"
SECRET = "s3gr3do-de-teste-com-mais-de-32-caracteres"
ORIGIN = f"chrome-extension://{EXT_ID}"
APP = "http://127.0.0.1:8000"
XSS = "<script>alert(1)</script>"
# Regiao ficticia: cerca de 10 km x 10 km
REGION = {"name": "Cidade Exemplo, MG", "lat": -20.0, "lng": -44.0,
          "south": -20.045, "north": -19.955, "west": -44.048, "east": -43.952}


def place(cid, name, phone="(31) 99999-0000", site="https://exemplo.com.br", rating=4.8, reviews=30, verified=True,
          hours=True, logo=True, address=None, lat=-20.0, lng=-44.0, categories=("Dentista",)):
    p = [None] * 210
    p[10] = f"0x0:{hex(int(cid))}"
    p[11] = name
    p[78] = f"ChIJ-{cid}"
    p[4] = [None] * 7 + [rating, reviews]
    p[13] = list(categories)
    p[39] = f"Rua Exemplo, {cid}" if address is None else address
    p[9] = [None, None, lat, lng]
    p[178] = [[phone]] if phone else None
    p[7] = [site] if site else None
    p[49] = None if verified else [None, "reivindicar"]
    p[203] = [[["segunda-feira", None, None, [["08:00–18:00"]]]]] if hours else None
    p[157] = "https://lh3.googleusercontent.com/logo" if logo else None
    return [None, p]


def page(*entries, ad=True):
    results = ([[None] * 6] if ad else []) + list(entries)
    return ")]}'\n" + json.dumps([None] * 64 + [results])


def full_page(start, n=20):
    return page(*[place(start + k, f"Negócio {start + k}") for k in range(n)])


class RegionTest(unittest.TestCase):
    def test_retangulo_do_nominatim(self):
        class R:
            status_code = 200

            def json(self):
                return [{"lat": "-19.9", "lon": "-43.9", "display_name": "Belo Horizonte, MG",
                         "boundingbox": ["-20.06", "-19.77", "-44.06", "-43.86"]}]
        calls = []
        found = region.find_region("Belo Horizonte", get=lambda *a, **k: calls.append(k) or R())
        self.assertEqual((found["south"], found["north"], found["west"], found["east"]), (-20.06, -19.77, -44.06, -43.86))
        self.assertEqual(calls[0]["params"]["countrycodes"], "br")
        self.assertIn("gbp-sealspro", calls[0]["headers"]["User-Agent"])

    def test_sem_resposta_ou_lixo(self):
        class R:
            status_code = 200

            def __init__(self, data):
                self.data = data

            def json(self):
                return self.data
        for data in ([], [{"lat": "x"}], [{"lat": "1", "lon": "1", "boundingbox": ["5", "1", "1", "2"]}]):
            self.assertIsNone(region.find_region("x", get=lambda *a, **k: R(data)), data)
        import requests
        self.assertIsNone(region.find_region("x", get=mock.Mock(side_effect=requests.ConnectionError())))


class PlanTest(unittest.TestCase):
    def test_grade_no_centro_das_celulas_e_pedidos_por_ponto(self):
        pts, view = plan.make_points(REGION, 3)
        self.assertEqual(len(pts), 9)
        self.assertAlmostEqual(pts[0]["lat"], -20.045 + 0.09 / 6)  # sudoeste primeiro
        self.assertAlmostEqual(pts[4]["lat"], -20.0)
        self.assertAlmostEqual(pts[4]["lng"], -44.0)
        self.assertTrue(config.VIEW_MIN_M <= view <= config.VIEW_MAX_M)
        reqs = plan.requests_for(pts, 3)
        self.assertEqual(len(reqs), 27)
        self.assertEqual([r[2] for r in reqs[:4]], [0, 20, 40, 0])  # as paginas de um ponto seguidas
        self.assertEqual(reqs[0][:2], reqs[2][:2])

    def test_bairro_pequeno_ganha_tamanho_minimo(self):
        tiny = {**REGION, "south": -20.0001, "north": -19.9999, "west": -44.0001, "east": -43.9999}
        *_, ns, ew = plan.area(tiny)
        self.assertAlmostEqual(ns, 2 * config.REGION_MIN_HALF_M, delta=1)
        self.assertGreaterEqual(ew, 2 * config.REGION_MIN_HALF_M - 1)

    def test_regiao_grande_demais(self):
        with self.assertRaises(plan.RegionError):
            plan.make_points({**REGION, "south": -22.0, "north": -18.0}, 3)

    def test_dentro_da_regiao_com_margem(self):
        self.assertTrue(plan.inside(REGION, -20.0, -44.0))
        self.assertTrue(plan.inside(REGION, -20.047, -44.0))  # na margem de 500 m
        self.assertFalse(plan.inside(REGION, -20.2, -44.0))
        self.assertIsNone(plan.inside(REGION, None, None))


class ReaderTest(unittest.TestCase):
    def test_campos_do_perfil(self):
        leads, organic = reader.read_page(page(place(10, "Clínica A", verified=False, categories=("Dentista", "Ortodontista"))))
        self.assertEqual(organic, 1)  # o anuncio nao conta
        l = leads[0]
        self.assertEqual((l["key"], l["cid"], l["placeId"]), ("ChIJ-10", "10", "ChIJ-10"))
        self.assertEqual((l["name"], l["phone"], l["website"]), ("Clínica A", "(31) 99999-0000", "https://exemplo.com.br"))
        self.assertEqual((l["rating"], l["reviews"], l["verified"]), (4.8, 30, False))
        self.assertEqual(l["categories"], ["Dentista", "Ortodontista"])
        self.assertEqual(l["hours"], {"segunda-feira": ["08:00–18:00"]})
        self.assertTrue(l["logo"])

    def test_sem_bloco_de_avaliacoes_e_zero(self):
        entry = place(5, "Novo")
        entry[1][4] = None
        lead = reader.read_page(page(entry))[0][0]
        self.assertEqual((lead["rating"], lead["reviews"]), (None, 0))
        entry[1][4] = [None] * 7 + [4.5]  # nota sem a quantidade: fica desconhecida
        self.assertIsNone(reader.read_page(page(entry))[0][0]["reviews"])

    def test_vazio_repetido_e_lixo(self):
        self.assertEqual(reader.read_page(")]}'\n" + json.dumps([None] * 10)), ([], 0))
        leads, organic = reader.read_page(page(place(1, "A"), place(1, "A")))
        self.assertEqual((len(leads), organic), (1, 2))
        for junk in ("", "nao e json", "{}", "[1, 2", None, 5):
            self.assertIsNone(reader.read_page(junk), junk)
        leads, _ = reader.read_page(page([None, [None] * 5], [None, "x"]))  # sem identificador
        self.assertEqual(leads, [])


class QualityTest(unittest.TestCase):
    def lead(self, **kw):
        base = {"phone": "1", "website": "https://exemplo.com.br", "hours": {"seg": ["8"]}, "logo": "u",
                "verified": True, "reviews": 30, "rating": 4.8}
        return {**base, **kw}

    def test_criterios_da_pre_analise(self):
        self.assertEqual(quality(self.lead())["score"], 100)
        q = quality(self.lead(website="https://instagram.com/x"))  # rede social = razoavel
        self.assertEqual((q["score"], q["fair"]), (92, 1))
        self.assertEqual(quality(self.lead(phone="", website="", reviews=0, rating=None))["score"], 42)  # 3 bons de 7
        self.assertEqual(quality(self.lead(rating=4.0))["fair"], 1)  # 3,5 a 4,4 = razoavel

    def test_quantidade_nao_informada_fica_fora(self):
        q = quality(self.lead(reviews=None, rating=5))
        item = next(i for i in q["items"] if i["id"] == "reviews_count")
        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(q["score"], 100)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(storage, "DATA", self.tmp.name),
                  mock.patch.object(storage, "DB", os.path.join(self.tmp.name, "t.db")),
                  mock.patch.object(pre_web, "extension_settings", lambda: (EXT_ID, SECRET)),
                  mock.patch.object(service, "locate", lambda text: dict(REGION))):  # nunca a internet
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(webapp.app, base_url=APP)

    def ext(self, path, body, origin=ORIGIN, secret=SECRET):
        headers = {"content-type": "application/json"}
        if origin is not None:
            headers["origin"] = origin
        if secret is not None:
            headers["x-seals-secret"] = secret
        return self.client.post(path, content=json.dumps(body), headers=headers)

    def page_post(self, path, body, origin=APP):
        return self.client.post(path, content=json.dumps(body),
                                headers={"content-type": "application/json", "origin": origin})

    def create(self, palavra="dentista", regiao="Cidade Exemplo", abrangencia="rapida"):
        r = self.client.post("/leads/nova", content=f"palavra={palavra}&regiao={regiao}&abrangencia={abrangencia}",
                             headers={"content-type": "application/x-www-form-urlencoded", "origin": APP},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("iniciar=1", r.headers["location"])
        return int(r.headers["location"].split("id=")[1].split("&")[0])

    def run_search(self, pages):
        """Cria a busca rapida (3x3, 2 paginas), pega a tarefa e manda as paginas dadas ({idx: texto}); devolve o id."""
        sid = self.create()
        t = self.ext("/leads/tarefa", {"id": sid}).json()
        self.assertTrue(t["ok"], t)
        for i, text in pages.items():
            self.assertTrue(self.ext("/leads/ponto", {"id": sid, "i": i, "text": text}).json()["ok"])
        return sid


class FlowTest(Base):
    def test_fluxo_completo(self):
        sid = self.create()
        self.assertIn("Buscar no Google Maps", self.client.get(f"/leads/busca?id={sid}").text)
        task = self.ext("/leads/tarefa", {"id": sid}).json()["task"]
        self.assertEqual(task["mode"], "leads")
        self.assertEqual(len(task["points"]), 18)  # 3x3, 2 paginas
        self.assertTrue(task["searchUrl"].startswith("https://www.google.com/maps/search/dentista/@"))
        self.assertEqual(task["view"], plan.make_points(REGION, 3)[1])
        # ponto 0: pagina cheia e depois incompleta; ponto 1: incompleta logo na primeira (pula a segunda)
        r0 = self.ext("/leads/ponto", {"id": sid, "i": 0, "text": full_page(100)}).json()
        self.assertEqual((r0["skip"], r0["received"]), (0, 1))
        r1 = self.ext("/leads/ponto", {"id": sid, "i": 1, "text": page(place(200, "Último"), place(100, "Negócio 100"))}).json()
        self.assertEqual(r1["skip"], 0)  # ja era a ultima pagina do ponto
        r2 = self.ext("/leads/ponto", {"id": sid, "i": 2, "text": page(place(100, "Negócio 100"), place(300, "Outro"))}).json()
        self.assertEqual((r2["skip"], r2["received"]), (1, 4))  # a pagina 2 do ponto 1 fica pulada
        for i in range(4, 18):
            self.ext("/leads/ponto", {"id": sid, "i": i, "text": page()})
        self.assertEqual(self.ext("/leads/fim", {"id": sid}).json()["status"], "pronta")
        with closing(storage.connect()) as db:
            s = storage.get_lead_search(db, sid)
        res = s["result"]
        self.assertEqual(res["total"], 22)  # 20 + "Último" + "Outro", sem repetir
        first = res["leads"][0]
        self.assertEqual((first["name"], first["hits"], first["order"]), ("Negócio 100", 3, 1))
        self.assertIn("quality", first)
        self.assertTrue(first["inside"])
        html = self.client.get(f"/leads/busca?id={sid}").text
        self.assertIn("22 leads", html)
        self.assertIn('id="ld-data"', html)
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "raw", "leads", str(sid), "000.json.gz")))

    def test_pagina_ilegivel_avisa_e_nenhuma_lida_e_erro(self):
        sid = self.run_search({0: "lixo", 1: full_page(1)})
        self.ext("/leads/fim", {"id": sid})
        with closing(storage.connect()) as db:
            res = storage.get_lead_search(db, sid)["result"]
        self.assertIn(0, res["unread"])
        self.assertIn("não chegaram ou não puderam ser lidas", res["warning"])
        sid2 = self.run_search({0: "lixo"})
        self.assertEqual(self.ext("/leads/fim", {"id": sid2}).json()["status"], "erro")

    def test_cancelada_ou_captcha_guarda_o_que_ja_veio(self):
        sid = self.run_search({0: full_page(1)})
        self.assertEqual(self.ext("/leads/fim", {"id": sid, "cancelled": True}).json()["status"], "cancelada")
        with closing(storage.connect()) as db:
            s = storage.get_lead_search(db, sid)
        self.assertEqual((s["status"], s["result"]["total"]), ("cancelada", 20))
        html = self.client.get(f"/leads/busca?id={sid}").text
        self.assertIn("Os leads lidos até ali estão abaixo", html)

    def test_pedido_fora_da_lista_e_busca_que_nao_esta_coletando(self):
        sid = self.create()
        self.assertFalse(self.ext("/leads/ponto", {"id": sid, "i": 0, "text": ""}).json()["ok"])  # ainda pendente
        self.ext("/leads/tarefa", {"id": sid})
        self.assertFalse(self.ext("/leads/tarefa", {"id": sid}).json()["ok"])  # a tarefa sai uma vez so
        self.assertFalse(self.ext("/leads/ponto", {"id": sid, "i": 18, "text": ""}).json()["ok"])

    def test_formulario_valida(self):
        for body in ("palavra=&regiao=BH&abrangencia=rapida", "palavra=x&regiao=&abrangencia=rapida",
                     "palavra=x&regiao=BH&abrangencia=enorme", f"palavra={'x' * 81}&regiao=BH&abrangencia=rapida"):
            r = self.client.post("/leads/nova", content=body, follow_redirects=False,
                                 headers={"content-type": "application/x-www-form-urlencoded", "origin": APP})
            self.assertEqual(r.status_code, 200, body)
            self.assertIn('class="notice error"', r.text)
        with mock.patch.object(service, "locate", lambda text: None):
            r = self.client.post("/leads/nova", content="palavra=x&regiao=Lugar+Nenhum&abrangencia=rapida",
                                 headers={"content-type": "application/x-www-form-urlencoded", "origin": APP})
            self.assertIn("Não foi possível localizar a região", r.text)
        with mock.patch.object(service, "locate", lambda text: {**REGION, "south": -25.0, "north": -15.0}):
            r = self.client.post("/leads/nova", content="palavra=x&regiao=Minas&abrangencia=rapida",
                                 headers={"content-type": "application/x-www-form-urlencoded", "origin": APP})
            self.assertIn("grande demais", r.text)

    def test_expirada_repetir_e_apagar(self):
        sid = self.create()
        with closing(storage.connect()) as db:
            db.execute("UPDATE lead_searches SET created_at='2020-01-01T00:00:00+00:00' WHERE id=?", (sid,))
            db.commit()
        self.assertIn("não foi iniciada a tempo", self.client.get(f"/leads/busca?id={sid}").text)
        self.assertFalse(self.ext("/leads/tarefa", {"id": sid}).json()["ok"])
        r = self.client.post(f"/leads/repetir?id={sid}", headers={"origin": APP}, follow_redirects=False)
        new = int(r.headers["location"].split("id=")[1].split("&")[0])
        self.assertNotEqual(new, sid)
        r = self.client.post(f"/leads/apagar?id={sid}", headers={"origin": APP}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        with closing(storage.connect()) as db:
            self.assertIsNone(storage.get_lead_search(db, sid))
        self.assertEqual(self.client.get("/leads").status_code, 200)


class NotesFavoritesCsvTest(Base):
    def setUp(self):
        super().setUp()
        self.sid = self.run_search({0: page(place(1, "=HYPERLINK(\"x\")", phone="+55 31 1234"),
                                            place(2, "Sem Site", site=None, phone=None))})
        self.ext("/leads/fim", {"id": self.sid})

    def test_nota_e_favorito_valem_para_o_negocio(self):
        self.assertEqual(self.page_post("/leads/nota", {"key": "ChIJ-1", "note": "Ligar segunda"}).status_code, 200)
        self.assertEqual(self.page_post("/leads/favorito", {"key": "ChIJ-1", "search": self.sid, "on": True}).status_code, 200)
        self.assertEqual(self.page_post("/leads/favorito", {"key": "ChIJ-9", "search": self.sid, "on": True}).status_code, 404)
        with closing(storage.connect()) as db:
            self.assertEqual(storage.lead_notes(db), {"ChIJ-1": "Ligar segunda"})
            self.assertEqual(list(storage.lead_favorites(db)), ["ChIJ-1"])
        html = self.client.get("/leads/favoritos").text
        self.assertIn("Leads favoritos", html)
        self.assertIn("Ligar segunda", html)
        # apagar a busca nao apaga nota nem favorito
        self.client.post(f"/leads/apagar?id={self.sid}", headers={"origin": APP})
        self.assertIn("Ligar segunda", self.client.get("/leads/favoritos").text)
        self.page_post("/leads/nota", {"key": "ChIJ-1", "note": "  "})
        self.page_post("/leads/favorito", {"key": "ChIJ-1", "on": False})
        with closing(storage.connect()) as db:
            self.assertEqual((storage.lead_notes(db), storage.lead_favorites(db)), ({}, {}))

    def test_planilha_todos_ou_filtrados_sem_formula(self):
        self.page_post("/leads/nota", {"key": "ChIJ-2", "note": "=1+1"})
        r = self.page_post("/leads/planilha.csv", {"search": self.sid, "keys": None})
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"Leads-{self.sid}-", r.headers["content-disposition"])
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(rows[0][0], "Nome")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][0], "'=HYPERLINK(\"x\")")  # texto, nao formula
        self.assertEqual(rows[1][3], "'+55 31 1234")
        self.assertEqual(rows[2][-1], "'=1+1")
        self.assertEqual(rows[1][11], "https://www.google.com/maps?cid=1")
        r = self.page_post("/leads/planilha.csv", {"search": self.sid, "keys": ["ChIJ-2"]})
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual([row[0] for row in rows[1:]], ["Sem Site"])
        self.assertEqual(self.page_post("/leads/planilha.csv", {"search": "x", "keys": None}).status_code, 400)
        self.assertEqual(self.page_post("/leads/planilha.csv", {"search": self.sid, "keys": [1]}).status_code, 400)

    def test_validacoes(self):
        self.assertEqual(self.page_post("/leads/nota", {"key": "", "note": "x"}).status_code, 400)
        self.assertEqual(self.page_post("/leads/nota", {"key": "k", "note": "x" * 2001}).status_code, 400)
        self.assertEqual(self.page_post("/leads/favorito", {"key": "k", "on": "sim"}).status_code, 400)
        r = self.client.post("/leads/nota", content="key=k&note=x",
                             headers={"content-type": "application/x-www-form-urlencoded", "origin": APP})
        self.assertEqual(r.status_code, 400)


class SecurityTest(Base):
    def test_pedidos_da_extensao_exigem_origem_e_segredo(self):
        sid = self.create()
        for path, body in (("/leads/tarefa", {"id": sid}), ("/leads/ponto", {"id": sid, "i": 0, "text": ""}),
                           ("/leads/fim", {"id": sid})):
            self.assertEqual(self.ext(path, body, secret=None).status_code, 403, path)
            self.assertEqual(self.ext(path, body, secret="x" * 40).status_code, 403, path)
            self.assertEqual(self.ext(path, body, origin="https://www.google.com").status_code, 403, path)
            self.assertEqual(self.ext(path, body, origin=None).status_code, 403, path)
        with closing(storage.connect()) as db:
            self.assertEqual(storage.get_lead_search(db, sid)["status"], "pendente")
        with mock.patch.object(pre_web, "extension_settings", lambda: ("", "")):
            self.assertEqual(self.ext("/leads/tarefa", {"id": sid}).status_code, 403)

    def test_corpo_invalido(self):
        self.assertEqual(self.ext("/leads/tarefa", {"id": "1"}).status_code, 400)
        self.assertEqual(self.ext("/leads/ponto", {"id": 1, "i": True, "text": ""}).status_code, 400)
        self.assertEqual(self.ext("/leads/fim", ["x"]).status_code, 400)

    def test_telas_recusam_outro_site(self):
        sid = self.create()
        for path in ("/leads/nota", "/leads/favorito", "/leads/planilha.csv"):
            self.assertEqual(self.page_post(path, {"key": "k", "note": "x", "on": True}, origin="https://evil.example")
                             .status_code, 403, path)
        r = self.client.post("/leads/nova", content="palavra=x&regiao=y&abrangencia=rapida",
                             headers={"content-type": "application/x-www-form-urlencoded",
                                      "origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.post(f"/leads/apagar?id={sid}", headers={"origin": "https://evil.example"})
                         .status_code, 403)

    def test_texto_do_maps_sai_escapado(self):
        sid = self.run_search({0: page(place(1, XSS, categories=(XSS,), address=XSS, site="javascript:alert(1)"))})
        self.ext("/leads/fim", {"id": sid})
        self.page_post("/leads/nota", {"key": "ChIJ-1", "note": XSS})
        for url in (f"/leads/busca?id={sid}", "/leads"):
            html = self.client.get(url).text
            self.assertNotIn(XSS, html, url)
        html = self.client.get(f"/leads/busca?id={sid}").text
        self.assertIn("\\u003cscript\\u003e", html)  # dentro do JSON da tela, escapado
        with open(os.path.join(webapp.HERE, "static", "leads.js"), encoding="utf-8") as f:
            js = f.read()
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertFalse(forbidden in js, forbidden)
        self.assertIn("const safeHref = (u) => (typeof u === \"string\" && /^https?:\\/\\//i.test(u) ? u : null);", js)


if __name__ == "__main__":
    unittest.main()
