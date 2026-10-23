import contextlib
import copy
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from starlette.testclient import TestClient

import coletar
import history
import service
import storage
from scoring import analyze, config, version
from collector.normalize import normalize
from tests.scoring.helpers import referencia
from tests.test_normalize import raw as raw_fixture
from web import app as webapp
from web import format as fmt

HEADERS = {"hx-request": "true"}


def snapshot_files(folder):
    out = {}
    for root, _, files in os.walk(folder):
        for f in files:
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, folder)] = hashlib.sha256(fh.read()).hexdigest()
    return out


class TempStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for p in (mock.patch.object(storage, "DATA", self.tmp.name),
                  mock.patch.object(storage, "DB", os.path.join(self.tmp.name, "t.db"))):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.db = storage.connect()
        self.addCleanup(self.db.close)
        storage.upsert_location(self.db, "locations/1", "accounts/1", "Clinica X", "BH", "Conta")
        storage.upsert_location(self.db, "locations/2", "accounts/1", "Clinica Y", "BH", "Conta")
        self.db.commit()
        self.n = 0

    def put_raw(self, raw, location="locations/1"):
        """Grava um bruto em data/raw (temporario) e devolve o caminho."""
        self.n += 1
        raw = copy.deepcopy(raw)
        raw["location"] = location
        folder = os.path.join(storage.raw_root(), location.replace("/", "_"))
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{self.n:04d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)
        return path

    def analysis(self, raw=None, kind="real", location="locations/1", **save_kw):
        raw = raw or raw_fixture()
        path = self.put_raw(raw, location)
        result = analyze(normalize({**raw, "location": location}))
        return storage.save_analysis(self.db, location, result, path, kind=kind, **save_kw)


# ---------------------------------------------------------------------------
# Banco: migracao com backup, versao e consultas
# ---------------------------------------------------------------------------

OLD_SCHEMA = [
    """CREATE TABLE locations (id TEXT PRIMARY KEY, account_id TEXT NOT NULL, title TEXT NOT NULL, city TEXT,
       active INTEGER NOT NULL DEFAULT 1, last_collected_at TEXT)""",
    """CREATE TABLE analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, location_id TEXT NOT NULL REFERENCES locations(id),
       analyzed_at TEXT NOT NULL, raw_path TEXT NOT NULL, score INTEGER, good INTEGER NOT NULL, fair INTEGER NOT NULL,
       bad INTEGER NOT NULL, unavailable INTEGER NOT NULL, result TEXT NOT NULL)""",
]


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(storage, "DATA", self.tmp.name),
                  mock.patch.object(storage, "DB", os.path.join(self.tmp.name, "gbp.db"))):
            p.start()
            self.addCleanup(p.stop)
        self.backups = os.path.join(self.tmp.name, "backups")

    def make_old_db(self):
        db = sqlite3.connect(storage.DB)
        for sql in OLD_SCHEMA:
            db.execute(sql)
        db.execute("INSERT INTO locations (id, account_id, title, city) VALUES ('locations/1', 'accounts/1', 'Clinica X', 'BH')")
        db.execute("INSERT INTO analyses (location_id, analyzed_at, raw_path, score, good, fair, bad, unavailable, result) "
                   "VALUES ('locations/1', '2026-10-08T21:33:14+00:00', '/x.json', 96, 19, 2, 0, 0, '{\"a\": 1}')")
        db.commit()
        db.close()

    def test_copia_antes_de_migrar_e_nada_se_perde(self):
        self.make_old_db()
        db = storage.connect()
        backups = os.listdir(self.backups)
        self.assertEqual(len(backups), 1)
        old = sqlite3.connect(os.path.join(self.backups, backups[0]))
        self.assertNotIn("kind", [r[1] for r in old.execute("PRAGMA table_info(analyses)")])  # copia do estado antigo
        self.assertEqual(old.execute("SELECT score FROM analyses").fetchone()[0], 96)
        old.close()
        row = db.execute("SELECT * FROM analyses").fetchone()
        self.assertEqual((row["score"], row["result"]), (96, '{"a": 1}'))
        self.assertEqual((row["kind"], row["engine_version"], row["config_hash"]), ("real", "desconhecida", None))
        self.assertEqual(db.execute("SELECT account_name FROM locations").fetchone()[0], "")
        db.close()

    def test_so_faz_uma_copia(self):
        self.make_old_db()
        storage.connect().close()
        storage.connect().close()
        storage.connect().close()
        self.assertEqual(len(os.listdir(self.backups)), 1)

    def test_banco_novo_nao_precisa_de_copia(self):
        storage.connect().close()
        self.assertFalse(os.path.exists(self.backups))

    def test_copia_e_feita_antes_de_qualquer_alteracao(self):
        self.make_old_db()
        order = []
        real_backup, real_pending = storage.backup_database, storage._pending_migrations
        with mock.patch.object(storage, "backup_database", lambda db: order.append("backup") or real_backup(db)):
            storage.connect().close()
        self.assertEqual(order, ["backup"])
        self.assertEqual(real_pending(sqlite3.connect(storage.DB)), [])


class VersionTest(unittest.TestCase):
    def test_versao_e_hash_do_config(self):
        self.assertTrue(version.ENGINE_VERSION)
        self.assertEqual(len(version.config_hash()), 64)
        self.assertEqual(version.config_hash(), version.config_hash())
        self.assertIn("reviews_unanswered", json.loads(version.config_json())["CONFIG"])

    def test_hash_muda_quando_o_config_muda(self):
        before = version.config_hash()
        with mock.patch.dict(config.CONFIG["videos"], {"recommended": 4}):
            self.assertNotEqual(version.config_hash(), before)
        self.assertEqual(version.config_hash(), before)

    def test_hash_muda_com_a_formula_da_nota_geral(self):
        before = version.config_hash()
        with mock.patch.dict(config.OVERALL["weights"], {"fair": 40}):
            self.assertNotEqual(version.config_hash(), before)


class StorageAnalysesTest(TempStorage):
    def test_analise_guarda_versao_motor_e_snapshot_do_config(self):
        self.analysis()
        row = storage.list_analyses(self.db, "locations/1")[0]
        self.assertEqual((row["engine_version"], row["config_hash"]), (version.ENGINE_VERSION, version.config_hash()))
        snap = self.db.execute("SELECT config_json FROM analyses").fetchone()[0]
        self.assertEqual(snap, version.config_json())

    def test_raw_root_segue_o_data_dos_testes(self):  # nunca escrever na pasta real do projeto
        path = storage.save_raw(self.db, "locations/1", raw_fixture())
        self.assertTrue(path.startswith(self.tmp.name))

    def test_latest_analysis_ignora_retroativas(self):
        real = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), kind="real")
        self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"), kind="retroativa")  # mais nova
        latest = storage.latest_analysis(self.db, "locations/1")
        self.assertEqual((latest["id"], latest["kind"]), (real, "real"))

    def test_sem_analise_real_nao_ha_ultima_analise(self):
        self.analysis(kind="retroativa")
        self.assertIsNone(storage.latest_analysis(self.db, "locations/1"))

    def test_list_analyses_traz_todas_em_ordem_cronologica(self):
        self.analysis(raw_fixture(collectedAt="2026-10-05T12:00:00+00:00"), kind="retroativa")
        self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), kind="real")
        self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"), kind="retroativa")
        rows = storage.list_analyses(self.db, "locations/1")
        self.assertEqual([r["analyzed_at"][:10] for r in rows], ["2026-10-01", "2026-10-05", "2026-10-08"])
        self.assertEqual([r["kind"] for r in rows], ["real", "retroativa", "retroativa"])
        self.assertNotIn("result", rows[0])

    def test_nada_e_podado(self):
        for day in range(1, 8):
            self.analysis(raw_fixture(collectedAt=f"2026-10-0{day}T12:00:00+00:00"))
        self.assertEqual(len(storage.list_analyses(self.db, "locations/1")), 7)

    def test_load_raw_file_so_le_dentro_de_data_raw(self):
        path = self.put_raw(raw_fixture())
        self.assertIsNotNone(storage.load_raw_file(path))
        outside = os.path.join(self.tmp.name, "fora.json")
        with open(outside, "w") as f:
            json.dump({"x": 1}, f)
        self.assertIsNone(storage.load_raw_file(outside))
        self.assertIsNone(storage.load_raw_file(os.path.join(storage.raw_root(), "..", "fora.json")))
        self.assertIsNone(storage.load_raw_file(os.path.join(storage.raw_root(), "nao-existe.json")))


class BackfillTest(TempStorage):
    def test_cria_retroativas_com_a_data_da_coleta_e_o_motor_atual(self):
        self.put_raw(raw_fixture(collectedAt="2026-10-01T10:00:00+00:00"))
        self.put_raw(raw_fixture(collectedAt="2026-10-03T10:00:00+00:00"))
        created, existing, ignored = service.backfill_retroactive(self.db)
        self.assertEqual((created, existing, ignored), (2, 0, 0))
        rows = storage.list_analyses(self.db, "locations/1")
        self.assertEqual([(r["kind"], r["analyzed_at"][:10]) for r in rows],
                         [("retroativa", "2026-10-01"), ("retroativa", "2026-10-03")])
        self.assertTrue(all(r["engine_version"] == version.ENGINE_VERSION and r["config_hash"] == version.config_hash()
                            for r in rows))

    def test_e_idempotente(self):
        self.put_raw(raw_fixture())
        service.backfill_retroactive(self.db)
        self.assertEqual(service.backfill_retroactive(self.db), (0, 1, 0))
        self.assertEqual(len(storage.list_analyses(self.db, "locations/1")), 1)

    def test_coleta_que_ja_tem_analise_real_nao_vira_retroativa(self):
        self.analysis(raw_fixture(), kind="real")
        self.assertEqual(service.backfill_retroactive(self.db)[0], 0)
        self.assertEqual([r["kind"] for r in storage.list_analyses(self.db, "locations/1")], ["real"])

    def test_retroativas_nao_viram_a_ultima_analise(self):
        self.put_raw(raw_fixture())
        service.backfill_retroactive(self.db)
        self.assertIsNone(storage.latest_analysis(self.db, "locations/1"))

    def test_bruto_de_outro_local_ou_desconhecido_e_ignorado(self):
        path = self.put_raw(raw_fixture(), "locations/1")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["location"] = "locations/999"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.assertEqual(service.backfill_retroactive(self.db), (0, 0, 1))

    def test_comando_retroativas(self):
        self.put_raw(raw_fixture())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            coletar.cmd_retroativas(self.db, None)
        self.assertIn("1 analises retroativas criadas", out.getvalue())


class ColetaGuardaAnaliseTest(TempStorage):
    def test_coletar_pela_linha_de_comando_cria_analise_real(self):
        row = storage.find_location(self.db, "Clinica X")
        raw = raw_fixture()
        raw["location"] = "locations/1"
        with mock.patch.object(coletar, "fetch_raw", return_value=raw), contextlib.redirect_stdout(io.StringIO()):
            coletar.coletar_um(self.db, row)
        rows = storage.list_analyses(self.db, "locations/1")
        self.assertEqual([(r["kind"], r["engine_version"]) for r in rows], [("real", version.ENGINE_VERSION)])
        self.assertIsNotNone(storage.latest_analysis(self.db, "locations/1"))


# ---------------------------------------------------------------------------
# Grafico, diferenca de itens e de dados (logica pura)
# ---------------------------------------------------------------------------

def a(id_, score, day, kind="real", ev="1", ch="h1"):
    return {"id": id_, "score": score, "analyzed_at": f"2026-10-{day:02d}T12:00:00+00:00", "kind": kind,
            "engine_version": ev, "config_hash": ch}


class ChartTest(unittest.TestCase):
    def test_nota_100_no_topo_e_0_na_base(self):
        c = history.build_chart([a(1, 100, 1), a(2, 0, 2)])
        top, bottom = c["points"][0]["y"], c["points"][1]["y"]
        self.assertAlmostEqual(top, c["plot_top"], places=0)
        self.assertAlmostEqual(bottom, c["plot_bottom"], places=0)

    def test_pontos_na_ordem_e_com_o_tipo(self):
        c = history.build_chart([a(1, 90, 1, "retroativa"), a(2, 95, 2, "real"), a(3, 80, 3, "retroativa")])
        self.assertEqual([(p["id"], p["kind"]) for p in c["points"]], [(1, "retroativa"), (2, "real"), (3, "retroativa")])
        xs = [p["x"] for p in c["points"]]
        self.assertEqual(xs, sorted(xs))
        self.assertAlmostEqual(xs[1] - xs[0], xs[2] - xs[1], places=0)  # igualmente espacados

    def test_um_ponto_fica_no_centro_e_sem_linha(self):
        c = history.build_chart([a(1, 70, 1)])
        self.assertEqual(c["n"], 1)
        mid = (c["left"] + c["right"]) / 2
        self.assertAlmostEqual(c["points"][0]["x"], mid, places=0)

    def test_sem_analises_nao_quebra(self):
        c = history.build_chart([])
        self.assertEqual((c["n"], c["points"], c["line"]), (0, [], ""))

    def test_analise_sem_nota_nao_entra_no_grafico(self):
        self.assertEqual(history.build_chart([a(1, None, 1), a(2, 80, 2)])["n"], 1)

    def test_marca_a_troca_de_versao_entre_dois_pontos(self):
        c = history.build_chart([a(1, 90, 1, ch="h1"), a(2, 91, 2, ch="h1"), a(3, 85, 3, ch="h2")])
        self.assertEqual(len(c["markers"]), 1)
        p = c["points"]
        self.assertTrue(p[1]["x"] < c["markers"][0]["x"] < p[2]["x"])
        self.assertIn("→", c["markers"][0]["text"])

    def test_mesma_versao_nao_marca(self):
        self.assertEqual(history.build_chart([a(1, 90, 1), a(2, 91, 2)])["markers"], [])

    def test_versao_desconhecida_conta_como_versao_diferente(self):
        c = history.build_chart([a(1, 90, 1, ev="desconhecida", ch=None), a(2, 91, 2)])
        self.assertEqual(len(c["markers"]), 1)

    def test_rotulos_do_eixo_x_sao_espacados_quando_ha_muitos_pontos(self):
        c = history.build_chart([a(i, 90, (i % 28) + 1) for i in range(1, 25)])
        self.assertLessEqual(len(c["xlabels"]), 9)
        self.assertEqual(history.build_chart([a(1, 90, 1), a(2, 90, 2)])["xlabels"].__len__(), 2)

    def test_faixas_do_medidor(self):
        c = history.build_chart([a(1, 90, 1)])
        self.assertEqual([b["cls"] for b in c["bands"]], ["bad", "fair", "good"])
        self.assertAlmostEqual(sum(b["h"] for b in c["bands"]), c["plot_bottom"] - c["plot_top"], places=3)

    def test_rotulo_da_versao(self):
        self.assertEqual(history.version_label(a(1, 1, 1)), "v1 · h1")
        self.assertEqual(history.version_label(a(1, 1, 1, ev="desconhecida", ch=None)), "desconhecida")


class ItemsDiffTest(unittest.TestCase):
    def test_so_o_que_mudou(self):
        ra = analyze(referencia())
        p = referencia()
        p["customerMedia"] = p["customerMedia"] * 3  # 1 -> 3 midias de clientes: 50 -> 100
        d = history.items_diff(ra, analyze(p))
        self.assertEqual([r["id"] for r in d["changed"]], [16])
        row = d["changed"][0]
        self.assertEqual((row["a_score"], row["b_score"], row["delta"]), (50, 100, 50))
        self.assertEqual(len(d["unchanged"]), 20)
        self.assertEqual(d["overall"]["d_score"], 2)  # (19*100 + 2*50)//21 = 95 -> (20*100 + 50)//21 = 97
        self.assertEqual((d["overall"]["d_fair"], d["overall"]["d_good"]), (-1, 1))

    def test_mudanca_de_status_sem_nota(self):  # indisponivel -> com nota
        pa = referencia()
        pa["collectionErrors"] = {"localPosts": "HTTP 500"}
        d = history.items_diff(analyze(pa), analyze(referencia()))
        row = d["changed"][0]
        self.assertEqual((row["id"], row["a_status"], row["b_status"], row["delta"]), (29, "unavailable", "good", None))

    def test_iguais(self):
        d = history.items_diff(analyze(referencia()), analyze(referencia()))
        self.assertEqual((d["changed"], d["overall"]["d_score"]), ([], 0))

    def test_item_so_de_um_lado(self):
        ra, rb = analyze(referencia()), analyze(referencia())
        rb["items"] = [i for i in rb["items"] if i["legacyId"] != 25]
        row = history.items_diff(ra, rb)["changed"][0]
        self.assertEqual((row["id"], row["b_status"], row["b"]), (25, "ausente", None))


class ProfileDiffTest(unittest.TestCase):
    def rows(self, pa, pb):
        return {r["label"]: r for r in history.profile_diff(pa, pb)}

    def test_contagens_e_datas(self):
        pa, pb = referencia(), referencia()
        pb["reviews"] = pb["reviews"] + [{"rating": 5, "createdAt": "2026-10-07T12:00:00+00:00", "hasComment": True, "replied": False}]
        pb["posts"] = pb["posts"] + [{"type": "STANDARD", "createdAt": "2026-10-08T00:00:00+00:00"}]
        pb["media"] = pb["media"] + [{"format": "VIDEO", "category": "ADDITIONAL", "createdAt": "2026-10-06T00:00:00Z", "url": "x"}]
        r = self.rows(pa, pb)
        self.assertEqual((r["Total de avaliações"]["a"], r["Total de avaliações"]["b"], r["Total de avaliações"]["delta"]), (22, 23, 1))
        self.assertEqual(r["Sem resposta"]["delta"], 1)
        self.assertEqual((r["Vídeos"]["a"], r["Vídeos"]["b"]), (2, 3))
        self.assertEqual(r["Mídias do proprietário"]["delta"], 1)
        self.assertEqual(r["Última postagem"]["b"], "2026-10-08")
        self.assertTrue(r["Última postagem"]["changed"])
        self.assertGreater(r["Última postagem"]["delta_days"], 0)
        self.assertEqual(r["Avaliação mais recente"]["b"], "2026-10-07")

    def test_estrelas_de_5_a_1(self):
        pa, pb = referencia(), referencia()
        pb["location"]["starDistribution"] = [20, 0, 0, 1, 1]
        r = self.rows(pa, pb)["Estrelas (5★ a 1★)"]
        self.assertEqual((r["a"], r["b"], r["changed"]), ([22, 0, 0, 0, 0], [20, 0, 0, 1, 1], True))

    def test_sem_mudanca(self):
        self.assertFalse(any(r["changed"] for r in history.profile_diff(referencia(), referencia())))

    def test_nome_e_descricao_em_texto(self):
        pa, pb = referencia(), referencia()
        pb["location"]["name"], pb["location"]["description"] = "Outro nome", "Nova descricao"
        r = self.rows(pa, pb)
        self.assertEqual((r["Nome"]["a"], r["Nome"]["b"]), (pa["location"]["name"], "Outro nome"))
        self.assertEqual(r["Descrição"]["b"], "Nova descricao")
        self.assertTrue(r["Nome"]["changed"] and r["Descrição"]["changed"])

    def test_nao_expoe_texto_de_avaliacoes(self):
        facts = history.facts(referencia())
        self.assertFalse([k for k in facts if "comment" in k.lower() and k != "no_comment"])
        self.assertEqual(facts["no_comment"], 6)  # so a contagem
        text_rows = [r["label"] for r in history.profile_diff(referencia(), referencia()) if r["kind"] == "text"]
        self.assertEqual(text_rows, ["Nome", "Descrição"])

    def test_data_de_1970_nao_conta_como_ultima_midia(self):
        p = referencia()
        p["media"] = [{"format": "PHOTO", "category": "PROFILE", "createdAt": "1970-01-01T00:00:00Z", "url": "x"}]
        self.assertIsNone(history.facts(p)["last_owner_media"])


class FormatTest(unittest.TestCase):
    def test_horario_de_brasilia(self):
        self.assertEqual(fmt.local_datetime("2026-10-08T21:33:14+00:00"), "08/10/2026 18:33")
        self.assertEqual(fmt.local_short("2026-10-09T01:44:57+00:00"), "08/10 22:44")

    def test_data_br(self):
        self.assertEqual((fmt.br_date("2026-09-30"), fmt.br_date(None)), ("30/09/2026", "—"))

    def test_tipo(self):
        self.assertEqual((fmt.kind_label("real"), fmt.kind_label("retroativa")), ("Real", "Retroativa"))


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------

class HistoryWebTest(TempStorage):
    def setUp(self):
        super().setUp()
        self.client = TestClient(webapp.app, base_url="http://127.0.0.1:8000")
        self.job = service.SyncJob()
        p = mock.patch.object(webapp, "sync_job", self.job)
        p.start()
        self.addCleanup(p.stop)

    def two_analyses(self):
        """A: 2 avaliacoes; B: 3 avaliacoes, mais midias e nome novo."""
        ra = raw_fixture(collectedAt="2026-10-01T12:00:00+00:00")
        rb = raw_fixture(collectedAt="2026-10-08T12:00:00+00:00")
        rb["reviews"] = rb["reviews"] + [{"starRating": "FIVE", "comment": "texto privado do cliente", "createTime": "2026-10-07T00:00:00Z"}]
        rb["info"] = {**rb["info"], "title": "Clinica X Renomeada", "profile": {"description": "Descricao nova do perfil"}}
        return self.analysis(ra), self.analysis(rb)

    # ---- historico ----
    def test_historico_lista_as_analises_e_desenha_o_grafico(self):
        self.two_analyses()
        self.analysis(raw_fixture(collectedAt="2026-10-05T12:00:00+00:00"), kind="retroativa")
        html = self.client.get("/historico?local=locations/1").text
        self.assertIn("<svg class=\"chart\"", html)
        self.assertEqual(html.count('<circle class="pt pt-real"'), 2 + 1 + 2)  # grafico + legenda + linhas da tabela
        self.assertIn('pt-retroativa', html)
        self.assertIn("3 análise(s) guardada(s)", html)
        self.assertIn("Análise retroativa", html)
        self.assertIn("calculada depois, com o motor atual", html)
        self.assertIn("Mudança de versão", html)

    def test_pontos_do_grafico_real_cheio_e_retroativa_vazia(self):
        self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), kind="real")
        self.analysis(raw_fixture(collectedAt="2026-10-05T12:00:00+00:00"), kind="retroativa")
        html = self.client.get("/historico?local=locations/1").text
        plot = html[html.index('<svg class="chart"'):html.index("</svg>")]
        self.assertEqual((plot.count("pt pt-real"), plot.count("pt pt-retroativa")), (1, 1))

    def test_tabela_traz_data_tipo_nota_contadores_e_versao(self):
        self.two_analyses()
        html = self.client.get("/historico?local=locations/1").text
        self.assertIn("08/10/2026 09:00", html)  # 12:00 UTC em Brasilia
        self.assertIn(f"v{version.ENGINE_VERSION} · {version.config_hash()[:8]}", html)
        for col in ("Nota geral", "Fraco", "Razoável", "Bom", "Indisp.", "Tipo"):
            self.assertIn(col, html)
        self.assertEqual(html.count('name="a" value='), 2)

    def test_formulario_de_comparacao_marca_a_ultima_contra_a_anterior(self):
        a_id, b_id = self.two_analyses()
        html = self.client.get("/historico?local=locations/1").text
        self.assertRegex(html, rf'name="a" value="{a_id}"[^>]*checked')
        self.assertRegex(html, rf'name="b" value="{b_id}"[^>]*checked')

    def test_historico_sem_analises_explica(self):
        html = self.client.get("/historico?local=locations/2").text
        self.assertIn("Nenhuma análise guardada", html)
        self.assertIn("retroativas", html)

    def test_historico_so_mostra_locais_ativos(self):
        storage.set_active(self.db, "locations/2", False)
        self.db.commit()
        self.assertNotIn("Clinica Y", self.client.get("/historico").text)

    def test_links_entre_as_telas(self):
        self.analysis()
        self.assertIn('href="/historico?local=locations/1"', self.client.get("/?local=locations/1").text)
        history_page = self.client.get("/historico?local=locations/1").text
        self.assertIn('href="/?local=locations/1"', history_page)
        self.assertIn("Voltar à análise atual", history_page)

    # ---- comparar ----
    def test_comparacao_mostra_itens_que_mudaram_e_dados(self):
        a_id, b_id = self.two_analyses()
        html = self.client.get(f"/comparar?a={a_id}&b={b_id}").text
        self.assertIn("O que mudou nos dados do perfil", html)
        self.assertIn("Total de avaliações", html)
        self.assertIn("Clinica X Renomeada", html)          # nome: antes e depois em texto
        self.assertIn("Descricao nova do perfil", html)     # descricao em texto
        self.assertNotIn("texto privado do cliente", html)  # texto de avaliacao de cliente nunca aparece
        self.assertIn("Mudou (+1)", html)
        self.assertIn("Itens que mudaram", html)

    def test_comparacao_sem_mudanca_de_item(self):
        a_id = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"))
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        html = self.client.get(f"/comparar?a={a_id}&b={b_id}").text
        self.assertIn("Nenhum item mudou", html)
        self.assertNotIn("Reavaliar as duas", html)  # mesma versao: nada a reavaliar

    def test_versoes_diferentes_avisam_e_oferecem_reavaliar(self):
        a_id = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), engine_version="0", config_hash="abc12345" + "0" * 56)
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        html = self.client.get(f"/comparar?a={a_id}&b={b_id}").text
        self.assertIn("versões diferentes", html)
        self.assertIn(f"/comparar?a={a_id}&amp;b={b_id}&amp;reavaliar=1", html)
        self.assertIn("v0 · abc12345", html)

    def test_versao_desconhecida_tambem_avisa(self):
        a_id = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), engine_version="desconhecida")
        self.db.execute("UPDATE analyses SET config_hash=NULL WHERE id=?", (a_id,))
        self.db.commit()
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        self.assertIn("versões diferentes", self.client.get(f"/comparar?a={a_id}&b={b_id}").text)

    def test_reavaliar_recalcula_com_o_motor_atual(self):
        # A guardada com notas "antigas" (adulteradas); reavaliando, o motor atual volta ao valor correto.
        raw_a = raw_fixture(collectedAt="2026-10-01T12:00:00+00:00")
        path = self.put_raw(raw_a)
        result = analyze(normalize({**raw_a, "location": "locations/1"}))
        for item in result["items"]:
            if item["legacyId"] == 0:
                item["score"], item["status"] = 0, "bad"
        a_id = storage.save_analysis(self.db, "locations/1", result, path, engine_version="0", config_hash="x" * 64)
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        guardadas = self.client.get(f"/comparar?a={a_id}&b={b_id}").text
        self.assertIn("Número de telefone", guardadas.split("Itens que mudaram")[1].split("sem mudança")[0])
        reavaliadas = self.client.get(f"/comparar?a={a_id}&b={b_id}&reavaliar=1").text
        self.assertIn("Notas reavaliadas com o motor atual", reavaliadas)
        self.assertIn("nada foi gravado", reavaliadas)
        self.assertIn("Nenhum item mudou", reavaliadas)
        self.assertIn("reavaliada com o motor atual", reavaliadas)

    def test_b_reavaliacao_nao_grava_nada(self):
        """(b) A reavaliacao e calculada em memoria: banco e arquivos ficam identicos."""
        raw_a = raw_fixture(collectedAt="2026-10-01T12:00:00+00:00")
        a_id = self.analysis(raw_a, engine_version="0", config_hash="y" * 64)
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        before = ([tuple(r) for r in self.db.execute("SELECT * FROM analyses ORDER BY id")],
                  [tuple(r) for r in self.db.execute("SELECT * FROM locations ORDER BY id")],
                  snapshot_files(storage.raw_root()))
        db_bytes = open(storage.DB, "rb").read()
        for _ in range(3):
            r = self.client.get(f"/comparar?a={a_id}&b={b_id}&reavaliar=1")
            self.assertEqual(r.status_code, 200)
        after = ([tuple(r) for r in self.db.execute("SELECT * FROM analyses ORDER BY id")],
                 [tuple(r) for r in self.db.execute("SELECT * FROM locations ORDER BY id")],
                 snapshot_files(storage.raw_root()))
        self.assertEqual(before, after)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0], 2)
        self.assertEqual(open(storage.DB, "rb").read(), db_bytes)  # nem um byte do banco mudou
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "backups")))

    def test_b_reavaliacao_nao_chama_nenhuma_gravacao(self):
        a_id = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), engine_version="0")
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        with mock.patch.object(storage, "save_analysis") as save, mock.patch.object(storage, "save_raw") as save_raw, \
                mock.patch.object(storage, "set_active") as set_active:
            self.client.get(f"/comparar?a={a_id}&b={b_id}&reavaliar=1")
        save.assert_not_called()
        save_raw.assert_not_called()
        set_active.assert_not_called()

    def test_reavaliar_sem_o_bruto_cai_para_as_notas_guardadas_e_avisa(self):
        a_id = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), engine_version="0")
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        os.remove(self.db.execute("SELECT raw_path FROM analyses WHERE id=?", (a_id,)).fetchone()[0])
        r = self.client.get(f"/comparar?a={a_id}&b={b_id}&reavaliar=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("O bruto da análise A não está mais disponível", r.text)
        self.assertIn("não podem ser comparados", r.text)

    def test_caminho_de_bruto_fora_de_data_raw_e_tratado_como_ausente(self):
        a_id = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"))
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        self.db.execute("UPDATE analyses SET raw_path='/etc/hosts' WHERE id=?", (a_id,))
        self.db.commit()
        r = self.client.get(f"/comparar?a={a_id}&b={b_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("O bruto da análise A não está mais disponível", r.text)

    def test_comparacao_invalida(self):
        a_id = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"))
        other = self.analysis(raw_fixture(collectedAt="2026-10-02T12:00:00+00:00"), location="locations/2")
        self.assertEqual(self.client.get(f"/comparar?a={a_id}&b={a_id}").status_code, 400)
        self.assertEqual(self.client.get(f"/comparar?a={a_id}&b={other}").status_code, 400)
        self.assertEqual(self.client.get(f"/comparar?a={a_id}&b=9999").status_code, 404)
        self.assertEqual(self.client.get("/comparar?a=x&b=1").status_code, 422)

    def test_comparacao_mostra_o_texto_novo_de_item_indisponivel_mesmo_em_analise_antiga(self):
        p = referencia()
        p["collectionErrors"] = {"media": "HTTP 500"}
        result = analyze(p)
        for item in result["items"]:
            if item["status"] == "unavailable":
                item["message"]["template"] = "Não foi possível avaliar este item: os dados de {sections} não puderam ser coletados."
        path = self.put_raw(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"))
        a_id = storage.save_analysis(self.db, "locations/1", result, path)
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"))
        html = self.client.get(f"/comparar?a={a_id}&b={b_id}").text
        self.assertIn("Não foi possível coletar este dado.", html)
        self.assertNotIn("dados de media", html)

    def test_comparar_retroativa_com_real(self):
        a_id = self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), kind="retroativa")
        b_id = self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"), kind="real")
        html = self.client.get(f"/comparar?a={a_id}&b={b_id}").text
        self.assertIn("Retroativa", html)
        self.assertIn("Real", html)

    # ---- (c) tela principal so considera analises reais ----
    def test_c_tela_principal_ignora_retroativas(self):
        real_day = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        self.analysis(raw_fixture(collectedAt=real_day), kind="real")
        self.analysis(raw_fixture(collectedAt=datetime.now(timezone.utc).isoformat()), kind="retroativa")  # mais nova
        html = self.client.get("/?local=locations/1").text
        self.assertIn("há 3 dias", html)  # 'Ultima atualizacao' vem da analise real, nao da retroativa recente

    def test_c_so_retroativas_a_tela_principal_diz_que_nao_ha_analise(self):
        self.analysis(kind="retroativa")
        html = self.client.get("/?local=locations/1").text
        self.assertIn("Ainda sem análise guardada", html)
        self.assertIn("ainda não foi analisado", html)
        self.assertNotIn("Última atualização:", html)

    def test_c_local_padrao_considera_so_analises_reais(self):
        self.analysis(raw_fixture(collectedAt="2026-10-01T12:00:00+00:00"), location="locations/1", kind="real")
        self.analysis(raw_fixture(collectedAt="2026-10-08T12:00:00+00:00"), location="locations/2", kind="retroativa")
        self.assertIn('<option value="locations/1" selected>', self.client.get("/").text)

    def test_c_analisar_cria_analise_real_com_versao(self):
        def fake(db, location):
            service.store_analysis(db, location["id"], {**raw_fixture(), "location": location["id"]},
                                   self.put_raw(raw_fixture()))
        with mock.patch.object(webapp, "run_analysis", fake):
            self.client.post("/analisar?local=locations/1", headers=HEADERS)
        rows = storage.list_analyses(self.db, "locations/1")
        self.assertEqual([(r["kind"], r["engine_version"]) for r in rows], [("real", version.ENGINE_VERSION)])

    def test_c_historico_mostra_as_retroativas_mesmo_assim(self):
        self.analysis(kind="retroativa")
        html = self.client.get("/historico?local=locations/1").text
        self.assertIn("Retroativa", html)
        self.assertIn("1 análise(s) guardada(s)", html)

    def test_seguranca_local_continua(self):
        self.assertEqual(TestClient(webapp.app, base_url="http://evil.example").get("/historico").status_code, 400)
        self.assertEqual(TestClient(webapp.app, base_url="http://evil.example").get("/comparar?a=1&b=2").status_code, 400)


if __name__ == "__main__":
    unittest.main()
