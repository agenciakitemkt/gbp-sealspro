"""Analise de Ranking (CLAUDE.md, secao 16): grade, leitura de um ponto, metricas, fluxo no app e seguranca dos
pedidos da extensao. Respostas da busca montadas aqui no formato da fonte D (sem dados reais)."""

import gzip
import json
import math
import os
import tempfile
import unittest
from contextlib import closing
from unittest import mock

from starlette.testclient import TestClient

import storage
from ranking import config, geocode, grid, history, metrics, reader, service
from web import app as webapp
from web import pre as pre_web

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pre", "maps")
EXT_ID = "abcdefghijklmnopabcdefghijklmnop"
SECRET = "s3gr3do-de-teste-com-mais-de-32-caracteres"
ORIGIN = f"chrome-extension://{EXT_ID}"
XSS = "<script>alert(1)</script>"
LOC = "locations/123"
CLIENT_CID = "1"  # CID do place_A.json (anonimizado: coordenadas 0, 0)


def place(cid, name, place_id=None, rating=4.5, reviews=10, category="Dentista", lat=0.0, lng=0.0):
    p = [None] * 80
    p[10] = f"0x0:{hex(int(cid))}"
    p[11] = name
    p[78] = place_id or f"ChIJ-{cid}"
    p[4] = [None] * 7 + [rating, reviews]
    p[13] = [category]
    p[39] = f"Rua Exemplo, {cid}"
    p[9] = [None, None, lat, lng]
    return [None, p]


def search(*entries, ad=True):
    results = ([[None] * 6] if ad else []) + list(entries)
    body = [None] * 64 + [results]
    return ")]}'\n" + json.dumps(body)


class GridTest(unittest.TestCase):
    def test_geometria_do_gbp_check(self):
        pts = grid.make_grid(-20.0, -44.0, 5, 2000)
        self.assertEqual(len(pts), 25)
        self.assertEqual(pts[12], {"i": 12, "lat": -20.0, "lng": -44.0})  # o centro e o ponto do meio
        span_lat = 4000 / 111320
        span_lng = 4000 / (111320 * math.cos(math.radians(-20.0)))
        self.assertAlmostEqual(pts[0]["lat"], -20.0 - span_lat / 2)  # sudoeste primeiro
        self.assertAlmostEqual(pts[0]["lng"], -44.0 - span_lng / 2)
        self.assertAlmostEqual(pts[24]["lat"], -20.0 + span_lat / 2)
        self.assertAlmostEqual(pts[4]["lng"], -44.0 + span_lng / 2)
        self.assertAlmostEqual(pts[1]["lng"] - pts[0]["lng"], span_lng / 4)
        self.assertEqual(grid.spacing_m(5, 2000), 1000)

    def test_lado_par_recusado(self):
        with self.assertRaises(ValueError):
            grid.make_grid(0, 0, 4, 1000)


class ReaderTest(unittest.TestCase):
    def test_fixture_da_busca_sem_anuncio(self):
        with open(os.path.join(FIX, "search_A.json"), encoding="utf-8") as f:
            results = reader.read_point(json.load(f))
        self.assertEqual([r["placeId"] for r in results],
                         ["ChIJ-exemplo-Concorrente 1", "ChIJ-exemplo-Concorrente 2", "ChIJ-exemplo-Concorrente 3"])
        self.assertEqual(results[0]["cid"], "90")
        self.assertEqual((results[0]["rating"], results[0]["reviews"], results[0]["category"]), (4.7, 29, "Faz-tudo"))

    def test_posicao_por_place_id_ou_cid_e_ate_20(self):
        text = search(*[place(100 + n, f"N{n}") for n in range(25)], place(7, "Cliente"))
        results = reader.read_point(text)
        self.assertEqual(len(results), config.RESULTS_PER_POINT)
        self.assertEqual(reader.position(results, "ChIJ-103", None), 4)
        self.assertEqual(reader.position(results, None, "104"), 5)
        self.assertIsNone(reader.position(results, "ChIJ-7", "7"))  # 26o: fora dos 20

    def test_repetido_conta_uma_vez(self):
        results = reader.read_point(search(place(1, "A"), place(1, "A"), place(2, "B")))
        self.assertEqual([r["cid"] for r in results], ["1", "2"])

    def test_lixo_nunca_quebra(self):
        for raw in (None, "", "lixo", "{}", ")]}'\n[1, 2]", 42, {"d": "x"}):
            out = reader.read_point(raw)
            self.assertTrue(out is None or out == [], raw)


class MetricsTest(unittest.TestCase):
    def test_como_o_gbp_check(self):
        # perfil de referência na referencia de 2026-10-11: so no centro, em 9o, numa 3x3 -> ARP 9, ATRP 19,67, SoLV 0
        s = metrics.summary([None, None, None, None, 9, None, None, None, None])
        self.assertEqual((s["arp"], s["atrp"], s["solv"], s["found"], s["points"]), (9.0, 19.67, 0.0, 1, 9))
        s = metrics.summary([1, 3, 4, None])
        self.assertEqual((s["arp"], s["atrp"], s["solv"]), (2.67, 7.25, 50.0))
        self.assertEqual(metrics.summary([])["atrp"], None)

    def test_concorrentes_ordenados_por_solv_e_atrp(self):
        a, b, c = {"placeId": "a"}, {"placeId": "b"}, {"placeId": "c"}
        comps = metrics.competitors([[a, b, c], [b, a], [c]])
        # todos com SoLV 66,67; a e b com ATRP 8 (empate: ordem de aparicao), c com 8,33
        self.assertEqual([x["placeId"] for x in comps], ["a", "b", "c"])
        self.assertEqual(comps[0]["positions"], [1, 2, None])
        self.assertEqual((comps[2]["solv"], comps[2]["atrp"]), (66.67, 8.33))


class Base(unittest.TestCase):
    @staticmethod
    def no_geocode(address):
        raise AssertionError("geocodificador chamado sem simulacao")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(storage, "DATA", self.tmp.name),
                  mock.patch.object(storage, "DB", os.path.join(self.tmp.name, "t.db")),
                  mock.patch.object(pre_web, "extension_settings", lambda: (EXT_ID, SECRET)),
                  mock.patch.object(service, "geocode", self.no_geocode)):  # nunca a internet nos testes
            p.start()
            self.addCleanup(p.stop)
        with closing(storage.connect()) as db:
            storage.upsert_location(db, LOC, "accounts/1", "Clínica Exemplo", "Cidade")
            storage.save_raw(db, LOC, {"collectedAt": "2026-10-11T12:00:00+00:00", "info": {
                "title": "Clínica Exemplo", "categories": {"primaryCategory": {"displayName": "Dentista"}},
                "metadata": {"placeId": "ChIJ-exemplo-A", "mapsUri": f"https://maps.google.com/maps?cid={CLIENT_CID}"},
                "storefrontAddress": {"addressLines": ["Rua Exemplo, 100"], "locality": "Cidade", "administrativeArea": "MG"}}})
        self.client = TestClient(webapp.app, base_url="http://127.0.0.1:8000")
        with open(os.path.join(FIX, "place_A.json"), encoding="utf-8") as f:
            self.place = json.dumps(json.load(f))

    def ext(self, path, body, origin=ORIGIN, secret=SECRET):
        headers = {"content-type": "application/json"}
        if origin is not None:
            headers["origin"] = origin
        if secret is not None:
            headers["x-seals-secret"] = secret
        return self.client.post(path, content=json.dumps(body), headers=headers)

    def create(self, keyword="dentista", grade=3, raio=1000, zoom=None):
        extra = f"&zoom={zoom}" if zoom else ""
        r = self.client.post("/ranking/nova", content=f"local={LOC}&palavra={keyword}&grade={grade}&raio={raio}{extra}",
                             headers={"content-type": "application/x-www-form-urlencoded",
                                      "origin": "http://127.0.0.1:8000"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("iniciar=1", r.headers["location"])  # a tela pede a extensao para comecar (clique unico)
        return int(r.headers["location"].split("id=")[1].split("&")[0])


class FlowTest(Base):
    def test_fluxo_completo(self):
        rid = self.create()
        page = self.client.get(f"/ranking/analise?id={rid}")
        self.assertIn("Ranking SealsPro", page.text)
        self.assertIn(f"https://www.google.com/maps?cid={CLIENT_CID}", page.text)

        r = self.ext("/ranking/inicio", {"place": self.place})
        self.assertEqual(r.status_code, 200, r.text)
        task = r.json()["task"]
        self.assertEqual((task["id"], task["keyword"], task["view"], len(task["points"])),
                         (rid, "dentista", config.VIEW_DISTANCE_M, 9))
        self.assertTrue(task["searchUrl"].startswith("https://www.google.com/maps/search/dentista/@0.0000000,0.0000000,"))
        # a analise ja foi iniciada: um segundo clique nao acha outra pendente
        self.assertEqual(self.ext("/ranking/inicio", {"place": self.place}).status_code, 409)

        client = place(CLIENT_CID, "Cliente", place_id="ChIJ-exemplo-A")
        for i in range(9):
            entries = [place(50, "Rival"), client] if i == 4 else [place(50, "Rival"), place(60, "Outro"), place(61, XSS)]
            r = self.ext("/ranking/ponto", {"id": rid, "i": i, "text": search(*entries)})
            self.assertEqual(r.json(), {"ok": True, "received": i + 1, "total": 9})
        self.assertEqual(self.ext("/ranking/fim", {"id": rid}).json()["status"], "pronta")

        with closing(storage.connect()) as db:
            res = storage.get_ranking(db, rid)["result"]
        self.assertEqual(res["own"]["positions"], [None] * 4 + [2] + [None] * 4)
        self.assertEqual((res["own"]["arp"], res["own"]["atrp"], res["own"]["solv"]), (2.0, 18.89, 11.11))
        self.assertEqual(res["competitors"][0]["name"], "Rival")
        self.assertEqual(res["competitors"][0]["solv"], 100.0)
        self.assertTrue(any(c["own"] for c in res["competitors"]))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, "raw", "ranking", str(rid), "004.json.gz")))
        with gzip.open(os.path.join(self.tmp.name, "raw", "ranking", str(rid), "004.json.gz"), "rt") as f:
            self.assertIn("Cliente", f.read())

        html = self.client.get(f"/ranking/analise?id={rid}").text
        self.assertNotIn(XSS, html)  # nome capturado sai escapado (tabela e dados do mapa)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("\\u003cscript\\u003e", html)
        lista = self.client.get(f"/ranking?local={LOC}").text
        self.assertIn("18,89", lista)

    def test_ponto_ilegivel_fica_fora_das_metricas(self):
        rid = self.create()
        self.ext("/ranking/inicio", {"place": self.place})
        for i in range(9):
            self.ext("/ranking/ponto", {"id": rid, "i": i, "text": "lixo" if i == 0 else search(place(50, "R"))})
        self.ext("/ranking/fim", {"id": rid})
        with closing(storage.connect()) as db:
            res = storage.get_ranking(db, rid)["result"]
        self.assertEqual(res["unread"], [0])
        self.assertEqual(res["own"]["points"], 8)

    def test_cancelada_e_ponto_fora_da_grade(self):
        rid = self.create()
        self.ext("/ranking/inicio", {"place": self.place})
        self.assertEqual(self.ext("/ranking/ponto", {"id": rid, "i": 9, "text": search()}).status_code, 409)
        self.assertEqual(self.ext("/ranking/fim", {"id": rid, "cancelled": True}).json()["status"], "cancelada")
        self.assertEqual(self.ext("/ranking/ponto", {"id": rid, "i": 0, "text": search()}).status_code, 409)

    def test_sem_analise_preparada_ou_outro_perfil(self):
        r = self.ext("/ranking/inicio", {"place": self.place})
        self.assertEqual(r.status_code, 409)
        self.assertIn("não há análise de ranking esperando", r.json()["error"])
        self.create()
        with open(os.path.join(FIX, "place_B.json"), encoding="utf-8") as f:
            other = json.dumps(json.load(f))
        self.assertEqual(self.ext("/ranking/inicio", {"place": other}).status_code, 409)

    def test_formulario_valida(self):
        for body in (f"local={LOC}&palavra=&grade=3&raio=1000", f"local={LOC}&palavra=x&grade=4&raio=1000",
                     f"local={LOC}&palavra=x&grade=3&raio=50"):
            r = self.client.post("/ranking/nova", content=body, headers={
                "content-type": "application/x-www-form-urlencoded", "origin": "http://127.0.0.1:8000"})
            self.assertEqual(r.status_code, 400, body)

    def test_formulario_de_outro_site_recusado(self):
        r = self.client.post("/ranking/nova", content=f"local={LOC}&palavra=x&grade=3&raio=1000",
                             headers={"content-type": "application/x-www-form-urlencoded",
                                      "origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)


class OneClickTest(Base):
    def test_tarefa_inicio_com_o_numero_da_analise(self):
        rid = self.create()
        page = self.client.get(f"/ranking/analise?id={rid}&iniciar=1").text
        self.assertIn(f'data-ext="{EXT_ID}"', page)
        self.assertIn('data-start="1"', page)
        r = self.ext("/ranking/tarefa", {"id": rid})
        self.assertEqual(r.json(), {"ok": True, "id": rid, "mapsUrl": f"https://www.google.com/maps?cid={CLIENT_CID}&hl=pt-BR"})
        self.assertEqual(self.ext("/ranking/inicio", {"place": self.place, "id": rid + 1}).status_code, 409)
        self.assertEqual(self.ext("/ranking/inicio", {"place": self.place, "id": rid}).status_code, 200)
        self.assertEqual(self.ext("/ranking/tarefa", {"id": rid}).status_code, 409)  # ja comecou

    def test_erro_antes_da_coleta_aparece_na_tela(self):
        rid = self.create()
        r = self.ext("/ranking/fim", {"id": rid, "error": "o perfil aberto no Maps não é o do cliente desta análise."})
        self.assertEqual(r.json()["status"], "erro")
        self.assertIn("não é o do cliente", self.client.get(f"/ranking/analise?id={rid}").text)

    def test_tarefa_exige_origem_e_segredo(self):
        rid = self.create()
        self.assertEqual(self.ext("/ranking/tarefa", {"id": rid}, secret=None).status_code, 403)
        self.assertEqual(self.ext("/ranking/tarefa", {"id": rid}, origin="http://127.0.0.1:8000").status_code, 403)


class HistoryTest(Base):
    def run_ranking(self, own_at, keyword="dentista", grade=3, raio=1000):
        """Analise completa em que o cliente aparece na posicao own_at[i] (None = nao aparece) de cada ponto."""
        rid = self.create(keyword=keyword, grade=grade, raio=raio)
        self.ext("/ranking/inicio", {"place": self.place})
        client = place(CLIENT_CID, "Cliente", place_id="ChIJ-exemplo-A")
        for i, pos in enumerate(own_at):
            others = [place(50, "Rival"), place(51, "Outro"), place(52, "Mais um")]
            entries = others if pos is None else others[:pos - 1] + [client] + others[pos - 1:]
            self.ext("/ranking/ponto", {"id": rid, "i": i, "text": search(*entries)})
        self.assertEqual(self.ext("/ranking/fim", {"id": rid}).json()["status"], "pronta")
        return rid

    def test_evolucao_e_comparacao(self):
        a = self.run_ranking([None] * 9)
        b = self.run_ranking([None] * 4 + [1] + [None] * 3 + [2])
        page = self.client.get(f"/ranking?local={LOC}").text
        self.assertIn("Evolução: “dentista”", page)
        self.assertIn('name="a"', page)
        # pedida ao contrario: o mais antigo continua sendo o "antes"
        html = self.client.get(f"/ranking/comparar?a={b}&b={a}").text
        self.assertIn(f"antes: ", html)
        self.assertLess(html.index(f"(#{a})"), html.index(f"(#{b})"))
        with closing(storage.connect()) as db:
            cmp = history.compare(storage.get_ranking(db, b), storage.get_ranking(db, a))
        self.assertEqual(cmp["a"]["id"], a)
        self.assertEqual(cmp["counts"], {"better": 2, "worse": 0, "same": 7, "unread": 0, "off": 0})
        found = next(m for m in cmp["metrics"] if m["metric"] == "found")
        atrp = next(m for m in cmp["metrics"] if m["metric"] == "atrp")
        self.assertEqual((found["a"], found["b"], found["trend"]), (0, 2, "better"))
        self.assertEqual(atrp["trend"], "better")  # ATRP menor e melhor
        self.assertTrue(any(r["own"] for r in cmp["competitors"]))

    def test_series_diferentes_nao_se_comparam(self):
        a = self.run_ranking([None] * 9)
        b = self.run_ranking([None] * 9, keyword="ortodontista")
        r = self.client.get(f"/ranking/comparar?a={a}&b={b}")
        self.assertEqual(r.status_code, 400)
        self.assertIn("mesma palavra-chave", r.text)
        self.assertEqual(self.client.get(f"/ranking/comparar?a={a}&b={a}").status_code, 400)
        self.assertEqual(self.client.get(f"/ranking/comparar?a={a}&b=999").status_code, 404)

    def test_grafico_inverte_a_posicao(self):
        rs = [{"id": 1, "created_at": "2026-10-01T00:00:00+00:00", "result": {"own": {"atrp": 21, "solv": 0}}},
              {"id": 2, "created_at": "2026-10-08T00:00:00+00:00", "result": {"own": {"atrp": 1, "solv": 100}}}]
        atrp, solv = history.line_chart(rs, "atrp"), history.line_chart(rs, "solv")
        self.assertGreater(atrp["points"][0]["y"], atrp["points"][1]["y"])  # 1o lugar fica em cima
        self.assertGreater(solv["points"][0]["y"], solv["points"][1]["y"])  # 100% fica em cima


class NoPublicAddressTest(Base):
    def place_without_address(self):
        data = json.loads(self.place)
        data[6][39] = None  # area de atendimento: o Maps nao tem endereco nem pin (centro do pais)
        data[6][9] = [None, None, -14.4095262, -51.3168626]
        return json.dumps(data)

    def test_centro_vem_do_endereco_cadastrado(self):
        rid = self.create()
        calls = []
        with mock.patch.object(service, "geocode", lambda a: calls.append(a) or (-19.9, -44.0, "endereço")):
            task = self.ext("/ranking/inicio", {"place": self.place_without_address()}).json()["task"]
        self.assertEqual(calls[0]["addressLines"], ["Rua Exemplo, 100"])
        self.assertEqual(task["points"][4], [-19.9, -44.0])  # o ponto central e o endereco, nao o centro do pais
        with closing(storage.connect()) as db:
            self.assertEqual(storage.get_ranking(db, rid)["center_source"], "endereço")
        self.assertIn("não tem endereço público", self.client.get(f"/ranking/analise?id={rid}").text)

    def test_sem_localizar_o_endereco_nao_roda_no_lugar_errado(self):
        rid = self.create()
        with mock.patch.object(service, "geocode", lambda a: None):
            r = self.ext("/ranking/inicio", {"place": self.place_without_address()})
        self.assertEqual(r.status_code, 409)
        with closing(storage.connect()) as db:
            got = storage.get_ranking(db, rid)
        self.assertEqual(got["status"], "erro")
        self.assertIn("endereço cadastrado", got["error"])


class GeocodeTest(unittest.TestCase):
    def fake_get(self, answers):
        calls = []

        def get(url, params, headers, timeout):
            calls.append(params)
            body = answers.pop(0) if answers else []
            return mock.Mock(status_code=200, json=lambda: body)
        get.calls = calls
        return get

    def test_rua_bairro_cidade_em_ordem(self):
        addr = {"addressLines": ["Rua X, 1"], "sublocality": "Glória", "locality": "Belo Horizonte",
                "administrativeArea": "MG", "postalCode": "30880-025"}
        get = self.fake_get([[], [], [{"lat": "-19.9", "lon": "-44.0"}]])
        self.assertEqual(geocode.geocode_address(addr, get=get), (-19.9, -44.0, "bairro"))
        self.assertEqual(get.calls[0]["street"], "Rua X, 1")
        self.assertTrue(all(c["countrycodes"] == "br" for c in get.calls))

    def test_sem_endereco_ou_sem_resposta(self):
        self.assertIsNone(geocode.geocode_address(None, get=self.fake_get([])))
        self.assertIsNone(geocode.geocode_address({"locality": "X"}, get=self.fake_get([[{"lat": "x"}]])))


class BatchTest(Base):
    def create_batch(self, palavras="dentista, ortodontista; implante\ndentista"):
        from urllib.parse import quote
        r = self.client.post("/ranking/nova", content=f"local={LOC}&palavra={quote(palavras)}&grade=3&raio=1000",
                             headers={"content-type": "application/x-www-form-urlencoded",
                                      "origin": "http://127.0.0.1:8000"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("/ranking/lote?id=", r.headers["location"])
        return int(r.headers["location"].split("id=")[1].split("&")[0])

    def run_points(self, rid):
        for i in range(9):
            self.ext("/ranking/ponto", {"id": rid, "i": i, "text": search(place(50, "R"))})

    def test_separa_as_palavras(self):
        self.assertEqual(service.split_keywords("a, b;c\n a ,, B"), ["a", "b", "c"])
        with self.assertRaises(service.RankingError):
            service.split_keywords("a,b,c,d,e,f")
        with self.assertRaises(service.RankingError):
            service.split_keywords(" , ;")

    def test_lote_roda_em_sequencia_com_o_mesmo_centro(self):
        batch = self.create_batch()
        with closing(storage.connect()) as db:
            items = storage.list_batch(db, batch)
        self.assertEqual([r["keyword"] for r in items], ["dentista", "ortodontista", "implante"])
        self.assertEqual(items[0]["id"], batch)
        page = self.client.get(f"/ranking/lote?id={batch}&iniciar=1").text
        self.assertIn(f'"seals:ranking-run", id: {batch}', page)  # o clique unico comeca pela primeira palavra
        # botao no Maps (sem numero): tambem comeca pela primeira palavra do lote
        task = self.ext("/ranking/inicio", {"place": self.place}).json()["task"]
        self.assertEqual((task["id"], task["keyword"]), (batch, "dentista"))
        self.run_points(batch)
        nxt = self.ext("/ranking/fim", {"id": batch}).json()["next"]
        self.assertEqual((nxt["id"], nxt["keyword"]), (items[1]["id"], "ortodontista"))
        self.assertEqual(nxt["points"], task["points"])  # mesmo centro, sem abrir o perfil de novo
        self.run_points(nxt["id"])
        nxt2 = self.ext("/ranking/fim", {"id": nxt["id"], "error": "falhou"}).json()["next"]  # erro: segue mesmo assim
        self.assertEqual(nxt2["keyword"], "implante")
        self.run_points(nxt2["id"])
        self.assertIsNone(self.ext("/ranking/fim", {"id": nxt2["id"]}).json()["next"])
        page = self.client.get(f"/ranking/lote?id={batch}").text
        self.assertIn("Melhor resultado", page)
        self.assertIn("Repetir as 3 palavras", page)
        status = self.client.get(f"/ranking/lote/status?id={batch}").json()["items"]
        self.assertEqual([x["status"] for x in status], ["pronta", "erro", "pronta"])

    def test_cancelar_cancela_o_resto_do_lote(self):
        batch = self.create_batch("dentista, ortodontista")
        self.ext("/ranking/inicio", {"place": self.place})
        r = self.ext("/ranking/fim", {"id": batch, "cancelled": True}).json()
        self.assertIsNone(r["next"])
        with closing(storage.connect()) as db:
            self.assertEqual([x["status"] for x in storage.list_batch(db, batch)], ["cancelada", "cancelada"])

    def test_bloqueio_do_google_para_o_lote(self):
        batch = self.create_batch("dentista, ortodontista")
        self.ext("/ranking/inicio", {"place": self.place})
        r = self.ext("/ranking/fim", {"id": batch, "error": config.BLOCKED_PREFIX + " (captcha) e a coleta parou."}).json()
        self.assertIsNone(r["next"])
        with closing(storage.connect()) as db:
            items = storage.list_batch(db, batch)
        self.assertEqual([x["status"] for x in items], ["erro", "cancelada"])
        self.assertIn("captcha", items[1]["error"])

    def test_grades_grandes(self):
        rid = self.create(grade=15, raio=3000)
        task = self.ext("/ranking/inicio", {"place": self.place}).json()["task"]
        self.assertEqual(len(task["points"]), 225)
        self.assertIn("15×15 (225 pontos, ~8 min)", self.client.get(f"/ranking?local={LOC}").text)

    def test_repetir_o_lote(self):
        batch = self.create_batch("dentista, ortodontista")
        self.ext("/ranking/inicio", {"place": self.place})
        self.ext("/ranking/fim", {"id": batch, "cancelled": True})
        r = self.client.post(f"/ranking/lote/repetir?id={batch}", headers={"origin": "http://127.0.0.1:8000"},
                             follow_redirects=False)
        new_batch = int(r.headers["location"].split("id=")[1].split("&")[0])
        with closing(storage.connect()) as db:
            self.assertEqual([x["keyword"] for x in storage.list_batch(db, new_batch)], ["dentista", "ortodontista"])
        self.assertEqual(self.client.get("/ranking/lote?id=999").status_code, 404)


class DisabledPointsTest(HistoryTest):
    def save(self, rid, disabled, origin="http://127.0.0.1:8000"):
        return self.client.post(f"/ranking/pontos?id={rid}", content=json.dumps({"disabled": disabled}),
                                headers={"content-type": "application/json", "origin": origin})

    def test_desligar_recalcula_e_vale_para_as_proximas(self):
        rid = self.run_ranking([1, None, None, None, 2, None, None, None, None])
        self.assertEqual(self.save(rid, [1, 2, 3]).json(), {"ok": True})
        with closing(storage.connect()) as db:
            r = storage.get_ranking(db, rid)
        self.assertEqual(r["disabled"], [1, 2, 3])
        own = r["result"]["own"]
        self.assertEqual((own["points"], own["found"], own["positions"][1]), (6, 2, None))
        self.assertEqual(r["result"]["disabled"], [1, 2, 3])
        page = self.client.get(f"/ranking/analise?id={rid}").text
        self.assertIn("3 pontos desligados", page)
        self.assertIn('title="Ponto desligado"', page)
        # proxima analise do mesmo local, grade e raio: ja nasce com os pontos desligados e nem busca neles
        nxt = self.create()
        task = self.ext("/ranking/inicio", {"place": self.place}).json()["task"]
        self.assertEqual(len(task["points"]), 6)
        for i in range(6):
            r = self.ext("/ranking/ponto", {"id": nxt, "i": i, "text": search(place(50, "R"))}).json()
            self.assertEqual(r["total"], 6)
        self.assertEqual(self.ext("/ranking/ponto", {"id": nxt, "i": 6, "text": search()}).status_code, 409)
        self.ext("/ranking/fim", {"id": nxt})
        with closing(storage.connect()) as db:
            got = storage.get_ranking(db, nxt)
            pts = storage.ranking_points(db, nxt)
        self.assertEqual(sorted(pts), [0, 4, 5, 6, 7, 8])  # pedido i -> indice da grade
        self.assertEqual((got["result"]["own"]["points"], got["result"]["unread"]), (6, []))

    def test_religar_ponto_nao_buscado_fica_sem_leitura(self):
        rid = self.run_ranking([None] * 9)
        self.save(rid, [0])
        nxt = self.create()
        self.ext("/ranking/inicio", {"place": self.place})
        for i in range(8):
            self.ext("/ranking/ponto", {"id": nxt, "i": i, "text": search(place(50, "R"))})
        self.ext("/ranking/fim", {"id": nxt})
        self.save(nxt, [])
        with closing(storage.connect()) as db:
            res = storage.get_ranking(db, nxt)["result"]
            self.assertEqual(storage.grid_pref(db, LOC, 3, 1000), [])
        self.assertEqual((res["unread"], res["own"]["points"]), ([0], 8))

    def test_validacoes(self):
        rid = self.run_ranking([None] * 9)
        self.assertEqual(self.save(rid, list(range(9))).status_code, 400)  # ao menos um ligado
        self.assertEqual(self.save(rid, [9]).status_code, 400)
        self.assertEqual(self.save(rid, ["1"]).status_code, 400)
        self.assertEqual(self.save(rid, [1], origin="https://evil.example").status_code, 403)
        pending = self.create()
        self.assertEqual(self.save(pending, [1]).status_code, 400)  # so analise pronta

    def test_comparacao_marca_os_desligados(self):
        a = self.run_ranking([None] * 9)
        b = self.run_ranking([1] + [None] * 8)
        self.save(b, [0])
        with closing(storage.connect()) as db:
            cmp = history.compare(storage.get_ranking(db, a), storage.get_ranking(db, b))
        self.assertEqual(cmp["points"][0]["trend"], "off")
        self.assertEqual(cmp["counts"]["off"], 1)


class ZoomTest(HistoryTest):
    def test_zoom_escolhido_vai_para_a_tarefa_e_o_repetir_mantem(self):
        rid = self.create(zoom=16000)
        task = self.ext("/ranking/inicio", {"place": self.place}).json()["task"]
        self.assertEqual(task["view"], 16000)
        self.ext("/ranking/fim", {"id": rid, "cancelled": True})
        r = self.client.post(f"/ranking/repetir?id={rid}", headers={"origin": "http://127.0.0.1:8000"},
                             follow_redirects=False)
        new_id = int(r.headers["location"].split("id=")[1].split("&")[0])
        with closing(storage.connect()) as db:
            self.assertEqual(storage.get_ranking(db, new_id)["view_m"], 16000)

    def test_zoom_invalido(self):
        r = self.client.post("/ranking/nova", content=f"local={LOC}&palavra=x&grade=3&raio=1000&zoom=123",
                             headers={"content-type": "application/x-www-form-urlencoded",
                                      "origin": "http://127.0.0.1:8000"})
        self.assertEqual(r.status_code, 400)

    def test_zooms_diferentes_nao_se_comparam(self):
        a = self.run_ranking([None] * 9)
        rid = self.create(zoom=4000)
        self.ext("/ranking/inicio", {"place": self.place})
        for i in range(9):
            self.ext("/ranking/ponto", {"id": rid, "i": i, "text": search(place(50, "R"))})
        self.ext("/ranking/fim", {"id": rid})
        r = self.client.get(f"/ranking/comparar?a={a}&b={rid}")
        self.assertEqual(r.status_code, 400)
        self.assertIn("zoom", r.text)


class ReminderTest(HistoryTest):
    def age(self, rid, iso):
        with closing(storage.connect()) as db:
            db.execute("UPDATE rankings SET created_at=? WHERE id=?", (iso, rid))
            db.commit()

    def test_lembrete_das_series_vencidas(self):
        old = self.run_ranking([None] * 9)
        self.age(old, "2026-08-01T12:00:00+00:00")
        with closing(storage.connect()) as db:
            due = history.due(storage.list_active_rankings(db))
        self.assertEqual([d["last"]["id"] for d in due], [old])
        self.assertEqual(due[0]["last"]["title"], "Clínica Exemplo")
        page = self.client.get(f"/ranking?local={LOC}").text
        self.assertIn("Para repetir", page)
        self.assertIn(f"/ranking/repetir?id={old}", page)
        self.assertIn("1 para repetir", self.client.get(f"/?local={LOC}").text)
        # repetida (pendente depois dela): sai do lembrete
        self.create()
        with closing(storage.connect()) as db:
            self.assertEqual(history.due(storage.list_active_rankings(db)), [])

    def test_recente_ou_de_local_inativo_nao_entra(self):
        self.run_ranking([None] * 9)
        with closing(storage.connect()) as db:
            self.assertEqual(history.due(storage.list_active_rankings(db)), [])
        old = self.run_ranking([None] * 9, keyword="ortodontista")
        self.age(old, "2026-08-01T12:00:00+00:00")
        with closing(storage.connect()) as db:
            storage.set_active(db, LOC, False)
            db.commit()
            self.assertEqual(history.due(storage.list_active_rankings(db)), [])


class RepeatAndExpiryTest(Base):
    def test_repetir_cria_outra_com_os_mesmos_dados(self):
        rid = self.create(keyword="dentista", grade=5, raio=2000)
        self.ext("/ranking/fim", {"id": rid, "error": "teste"})
        r = self.client.post(f"/ranking/repetir?id={rid}", headers={"origin": "http://127.0.0.1:8000"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("iniciar=1", r.headers["location"])
        new_id = int(r.headers["location"].split("id=")[1].split("&")[0])
        with closing(storage.connect()) as db:
            new = storage.get_ranking(db, new_id)
        self.assertEqual((new["keyword"], new["grid_size"], new["radius_m"], new["status"]), ("dentista", 5, 2000, "pendente"))
        self.assertIn("Repetir análise", self.client.get(f"/ranking/analise?id={rid}").text)

    def test_pendente_antiga_aparece_expirada_e_nao_e_aceita(self):
        rid = self.create()
        with closing(storage.connect()) as db:
            db.execute("UPDATE rankings SET created_at='2026-01-01T00:00:00+00:00' WHERE id=?", (rid,))
            db.commit()
        self.assertEqual(self.client.get(f"/ranking/status?id={rid}").json()["status"], "expirada")
        self.assertIn("Expirada", self.client.get(f"/ranking?local={LOC}").text)
        self.assertIn("expirou", self.client.get(f"/ranking/analise?id={rid}").text)
        self.assertEqual(self.ext("/ranking/tarefa", {"id": rid}).status_code, 409)
        self.assertEqual(self.ext("/ranking/inicio", {"place": self.place}).status_code, 409)


class SecurityTest(Base):
    def test_pedidos_da_extensao_exigem_origem_e_segredo(self):
        rid = self.create()
        for path, body in (("/ranking/inicio", {"place": self.place}), ("/ranking/ponto", {"id": rid, "i": 0, "text": ""}),
                           ("/ranking/fim", {"id": rid})):
            self.assertEqual(self.ext(path, body, secret=None).status_code, 403, path)
            self.assertEqual(self.ext(path, body, secret="x" * 40).status_code, 403, path)
            self.assertEqual(self.ext(path, body, origin="https://www.google.com").status_code, 403, path)
            self.assertEqual(self.ext(path, body, origin=None).status_code, 403, path)
        with closing(storage.connect()) as db:
            self.assertEqual(storage.get_ranking(db, rid)["status"], "pendente")

    def test_sem_configuracao_nada_entra(self):
        self.create()
        with mock.patch.object(pre_web, "extension_settings", lambda: ("", "")):
            self.assertEqual(self.ext("/ranking/inicio", {"place": self.place}).status_code, 403)

    def test_corpo_invalido(self):
        self.assertEqual(self.ext("/ranking/inicio", {"place": 1}).status_code, 400)
        self.assertEqual(self.ext("/ranking/ponto", {"id": "1", "i": 0, "text": ""}).status_code, 400)
        self.assertEqual(self.ext("/ranking/fim", ["x"]).status_code, 400)


class IdentityTest(Base):
    def test_sem_coleta_nao_cria(self):
        with closing(storage.connect()) as db:
            storage.upsert_location(db, "locations/9", "accounts/1", "Sem coleta", "Cidade")
            with self.assertRaises(service.RankingError):
                service.new_ranking(db, {"id": "locations/9"}, "x", 3, 1000)


if __name__ == "__main__":
    unittest.main()
