"""Pre Analise no app: /pre/captura (origem da extensao + segredo), /pre/ping, tabela pre_analyses e tela /pre.
Texto capturado e nao confiavel: a tela escapa tudo (nome, descricao, categoria, site, avaliacoes)."""

import copy
import json
import os
import re
import sqlite3
import tempfile
import unittest
from unittest import mock

from starlette.testclient import TestClient

import gbp_auth
import storage
from collector_pre.maps_reader import batchexecute
from scoring.pre.version import PRE_ENGINE_VERSION
from web import app as webapp
from web import pre as pre_web

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pre", "maps")
EXT_ID = "abcdefghijklmnopabcdefghijklmnop"
SECRET = "s3gr3do-de-teste-com-mais-de-32-caracteres"
ORIGIN = f"chrome-extension://{EXT_ID}"
XSS = "<script>alert(1)</script>"


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def capture(**changes):
    cap = {"capturedAt": "2026-10-09T23:00:00+00:00", "place": json.dumps(load("place_B.json")),
           "reviews": load("reviews_B.json"), "photosOwner": None, "photosVideos": None, "search": None,
           "extensionErrors": []}
    cap.update(changes)
    return cap


def wrb(inner, rpc="qv9Egd"):
    body = json.dumps([["wrb.fr", rpc, json.dumps(inner)]])
    return f")]}}'\n\n{len(body)}\n{body}\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(storage, "DATA", self.tmp.name),
                  mock.patch.object(storage, "DB", os.path.join(self.tmp.name, "t.db")),
                  mock.patch.object(pre_web, "extension_settings", lambda: (EXT_ID, SECRET))):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(webapp.app, base_url="http://127.0.0.1:8000")

    def post(self, body, origin=ORIGIN, secret=SECRET, path="/pre/captura", content_type="application/json"):
        headers = {"content-type": content_type}
        if origin is not None:
            headers["origin"] = origin
        if secret is not None:
            headers["x-seals-secret"] = secret
        data = body if isinstance(body, (bytes, str)) else json.dumps(body)
        return self.client.post(path, content=data, headers=headers)


class CapturaTest(Base):
    def test_captura_valida_grava_bruto_e_analise(self):
        r = self.post(capture())
        self.assertEqual(r.status_code, 200)
        aid = r.json()["id"]
        self.assertEqual(r.json()["url"], f"/pre?id={aid}")
        db = storage.connect()
        self.addCleanup(db.close)
        a = storage.get_pre_analysis(db, aid)
        self.assertEqual(a["engine_version"], PRE_ENGINE_VERSION)
        self.assertTrue(a["config_hash"])
        self.assertEqual(a["kind"], "real")
        self.assertTrue(a["raw_path"].startswith(os.path.join(self.tmp.name, "raw", "pre") + os.sep))
        with open(a["raw_path"], encoding="utf-8") as f:
            self.assertEqual(json.load(f)["capturedAt"], "2026-10-09T23:00:00+00:00")
        self.assertEqual(a["result"]["warnings"], a["warnings"])

    def test_avisos_sao_guardados_e_mostrados(self):
        r = self.post(capture(reviews=load("reviews_B.json")[::-1]))  # fora de ordem: gera aviso
        db = storage.connect()
        self.addCleanup(db.close)
        a = storage.get_pre_analysis(db, r.json()["id"])
        self.assertTrue(any("mais recente para a mais antiga" in w for w in a["warnings"]))
        html = self.client.get(f"/pre?id={a['id']}").text
        self.assertIn("Avisos da coleta", html)
        self.assertIn("mais recente para a mais antiga", html)

    def test_quantos_itens_foram_avaliados_e_aviso_quando_faltam_3_ou_mais(self):
        aid = self.post(capture()).json()["id"]  # sem galeria, busca, postagens, redes e 360
        db = storage.connect()
        self.addCleanup(db.close)
        o = storage.get_pre_analysis(db, aid)["result"]["overall"]
        evaluated = o["good"] + o["fair"] + o["bad"]
        html = self.client.get(f"/pre?id={aid}").text
        self.assertIn(f"{evaluated} de 20 itens avaliados", html)
        self.assertIn(f"Faltam {20 - evaluated} de 20 itens.", html)
        self.assertIn(f"{evaluated} de 20", self.client.get("/pre").text)

    def test_sem_aviso_forte_quando_faltam_menos_de_3(self):
        from scoring.pre import analyze
        from tests.scoring.pre.helpers import profile
        result = analyze(profile(notCollected=["photos_360", "last_post"]))
        db = storage.connect()
        self.addCleanup(db.close)
        aid = storage.save_pre_analysis(db, profile(), result, "/tmp/x.json", "3", "h", "{}")
        html = self.client.get(f"/pre?id={aid}").text
        self.assertIn("18 de 20 itens avaliados", html)
        self.assertNotIn("Faltam", html)

    def test_tela_e_lista(self):
        aid = self.post(capture()).json()["id"]
        html = self.client.get(f"/pre?id={aid}").text
        self.assertIn("Itens avaliados", html)
        self.assertIn("Não avaliados nesta pré análise", html)
        self.assertIn(f'href="/pre?id={aid}"', self.client.get("/pre").text)
        self.assertEqual(self.client.get("/pre?id=999").status_code, 404)


class AutorizacaoTest(Base):
    def test_sem_origem_da_extensao_e_recusado(self):
        for origin in (None, "https://www.google.com", "chrome-extension://outraextensaoabcdefghijklmnopab",
                       "http://127.0.0.1:8000", ORIGIN + "x", "null"):
            self.assertEqual(self.post(capture(), origin=origin).status_code, 403, origin)

    def test_segredo_errado_ou_ausente_e_recusado(self):
        for secret in (None, "", "errado", SECRET[:-1], SECRET + "x"):
            self.assertEqual(self.post(capture(), secret=secret).status_code, 403, secret)

    def test_sem_configuracao_nada_entra(self):
        for settings in (("", ""), (EXT_ID, ""), ("", SECRET), ("ID-INVALIDO", SECRET), (EXT_ID, "curto")):
            with mock.patch.object(pre_web, "extension_settings", lambda s=settings: s):
                self.assertEqual(self.post(capture(), origin=f"chrome-extension://{settings[0]}",
                                           secret=settings[1]).status_code, 403, settings)

    def test_recusa_nao_diz_o_motivo(self):
        self.assertEqual(self.post(capture(), secret="errado").text, "Não autorizado.")
        self.assertEqual(self.post(capture(), origin="https://evil.example").text, "Não autorizado.")

    def test_formato_do_corpo(self):
        self.assertEqual(self.post("{}", content_type="text/plain").status_code, 415)
        self.assertEqual(self.post(b"{nao e json").status_code, 400)
        self.assertEqual(self.post([1, 2]).status_code, 400)
        with mock.patch.object(pre_web, "MAX_BYTES", 100):
            self.assertEqual(self.post(capture()).status_code, 413)

    def test_nada_e_gravado_quando_recusa(self):
        self.post(capture(), secret="errado")
        db = storage.connect()
        self.addCleanup(db.close)
        self.assertEqual(storage.list_pre_analyses(db), [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "raw", "pre")))

    def test_ping(self):
        self.assertEqual(self.post({}, path="/pre/ping").status_code, 204)
        self.assertEqual(self.post({}, path="/pre/ping", secret="errado").status_code, 403)
        self.assertEqual(self.post({}, path="/pre/ping", origin="https://www.google.com").status_code, 403)

    def test_outras_rotas_continuam_protegidas_contra_a_origem_da_extensao(self):
        r = self.client.post("/analisar?local=x", headers={"origin": ORIGIN, "x-seals-secret": SECRET})
        self.assertEqual(r.status_code, 403)

    def test_host_que_nao_e_local_e_recusado(self):
        r = TestClient(webapp.app, base_url="http://evil.example").post(
            "/pre/captura", content=json.dumps(capture()),
            headers={"origin": ORIGIN, "x-seals-secret": SECRET, "content-type": "application/json"})
        self.assertEqual(r.status_code, 400)

    def test_sem_cabecalhos_cors(self):
        r = self.post(capture())
        self.assertNotIn("access-control-allow-origin", {k.lower() for k in r.headers})


class TextoNaoConfiavelTest(Base):
    def hostile_capture(self):
        place = load("place_B.json")
        place[6][11] = XSS                                # nome
        place[6][13] = ['<img src=x onerror="alert(2)">']  # categoria
        place[6][154][0][0] = "Descrição " + XSS
        place[6][7][0] = "javascript:alert(3)"             # site
        place[6][39] = "<b>endereço</b>"
        pages = load("reviews_B.json")
        inner = batchexecute(pages[0])
        inner[2][0][0][2][15] = [[XSS]]                    # texto de uma avaliacao
        pages[0] = wrb(inner)
        return capture(place=json.dumps(place), reviews=pages)

    def test_tudo_sai_escapado(self):
        aid = self.post(self.hostile_capture()).json()["id"]
        for html in (self.client.get(f"/pre?id={aid}").text, self.client.get("/pre").text):
            self.assertNotIn("<script>alert", html)
            self.assertNotIn("<img src=x", html)
            self.assertNotIn("<b>endereço</b>", html)
            self.assertNotRegex(html, r'href="javascript:')
        detail = self.client.get(f"/pre?id={aid}").text
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", detail)
        self.assertIn("&lt;img src=x", detail)
        self.assertIn("javascript:alert(3)", detail)  # aparece so como texto

    def test_texto_de_avaliacao_nunca_aparece(self):
        hostile = self.hostile_capture()
        place = json.loads(hostile["place"])
        place[6][11] = "Nome comum"
        place[6][154][0][0] = "Descrição comum"
        hostile["place"] = json.dumps(place)
        aid = self.post(hostile).json()["id"]
        html = self.client.get(f"/pre?id={aid}").text
        self.assertNotIn("alert(1)", html)  # so a avaliacao tinha esse texto: ela nao e mostrada de jeito nenhum

    def test_link_capturado_so_vira_href_se_for_http(self):
        self.assertIsNone(pre_web.safe_url("javascript:alert(1)"))
        self.assertIsNone(pre_web.safe_url("data:text/html,x"))
        self.assertIsNone(pre_web.safe_url(" javascript:x"))
        self.assertEqual(pre_web.safe_url("https://example.com/"), "https://example.com/")

    def test_templates_sem_safe_e_com_autoescape(self):
        from report import render
        folders = (os.path.join(os.path.dirname(webapp.__file__), "templates"),
                   os.path.join(os.path.dirname(render.__file__), "templates"))
        for folder in folders:
            for name in os.listdir(folder):
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    self.assertNotRegex(f.read(), r"\|\s*safe\b", name)
        self.assertTrue(webapp.templates.env.autoescape("pre.html"))
        self.assertTrue(render._env.autoescape("relatorio.html"))  # PDF: o da Pre Analise (fase 3) reaproveita


class TabelaTest(unittest.TestCase):
    def test_banco_antigo_ganha_a_tabela_com_copia_antes(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(storage, "DATA", tmp), \
                mock.patch.object(storage, "DB", os.path.join(tmp, "gbp.db")):
            old = sqlite3.connect(os.path.join(tmp, "gbp.db"))
            old.execute(storage._LOCATIONS_DDL)
            old.execute(storage._ANALYSES_DDL)
            old.commit()
            old.close()
            db = storage.connect()
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("pre_analyses", tables)
            db.close()
            self.assertEqual(len(os.listdir(os.path.join(tmp, "backups"))), 1)
            storage.connect().close()  # segunda vez: nada a migrar, nenhuma copia nova
            self.assertEqual(len(os.listdir(os.path.join(tmp, "backups"))), 1)


class EnvTest(unittest.TestCase):
    def test_app_le_id_e_segredo_so_do_env_da_raiz(self):
        import serve  # noqa: F401  (o serve.py sobe este mesmo app: web.app:app)
        with tempfile.TemporaryDirectory() as tmp:
            project, skill = os.path.join(tmp, ".env"), os.path.join(tmp, "skill.env")
            with open(skill, "w") as f:
                f.write(f'GBP_EXTENSION_ID="{EXT_ID}"\nGBP_EXTENSION_SECRET="{SECRET}"\n')
            with mock.patch.object(gbp_auth, "ENV_PATH", project), mock.patch.object(gbp_auth, "FALLBACK_ENV", skill):
                self.assertEqual(pre_web.extension_settings(), ("", ""))  # o da skill nao vale
                gbp_auth.save_env_value("GBP_EXTENSION_ID", EXT_ID)
                gbp_auth.save_env_value("GBP_EXTENSION_SECRET", SECRET)
                self.assertEqual(pre_web.extension_settings(), (EXT_ID, SECRET))

    def test_env_da_raiz_e_o_padrao_e_fica_fora_do_git(self):
        import subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertEqual(gbp_auth.ENV_PATH, os.path.join(root, ".env"))
        self.assertEqual(subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=root).returncode, 0)

    def test_comandos_gravam_no_env_sem_tocar_no_resto(self):
        import coletar
        with tempfile.TemporaryDirectory() as tmp:
            env = os.path.join(tmp, ".env")
            with open(env, "w") as f:
                f.write('GBP_CLIENT_ID="cliente"\n')
            with mock.patch.object(gbp_auth, "ENV_PATH", env), \
                    mock.patch.object(gbp_auth, "FALLBACK_ENV", os.path.join(tmp, "nao-existe")), \
                    mock.patch("builtins.print") as printed:
                coletar.cmd_segredo_extensao(None, mock.Mock(novo=False))
                secret = printed.call_args_list[-1].args[0]
                self.assertGreaterEqual(len(secret), 32)
                with self.assertRaises(SystemExit):           # nao troca sem --novo
                    coletar.cmd_segredo_extensao(None, mock.Mock(novo=False))
                coletar.cmd_id_extensao(None, mock.Mock(id=EXT_ID))
                with self.assertRaises(SystemExit):
                    coletar.cmd_id_extensao(None, mock.Mock(id="nao-e-id"))
            with open(env, encoding="utf-8") as f:
                text = f.read()
            self.assertIn('GBP_CLIENT_ID="cliente"', text)
            self.assertIn(f'GBP_EXTENSION_SECRET="{secret}"', text)
            self.assertIn(f'GBP_EXTENSION_ID="{EXT_ID}"', text)
            self.assertEqual(os.stat(env).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
