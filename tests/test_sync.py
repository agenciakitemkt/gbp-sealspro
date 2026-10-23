import os
import tempfile
import time
import unittest
from unittest import mock

import requests
from starlette.testclient import TestClient

import service
import storage
from web import app as webapp

ACCOUNTS = [{"name": "accounts/1", "accountName": "Conta A"}, {"name": "accounts/2", "accountName": "Conta B"}]
LOCATIONS = {
    "accounts/1": [{"name": "locations/1", "title": "Clinica Um", "storefrontAddress": {"locality": "BH"}},
                   {"name": "locations/99999999999999999999", "title": "Salao Antigo"}],  # ex-cliente conhecido
    "accounts/2": [{"name": "locations/3", "title": "Clinica Tres"}],
}


def fake_paginate(api, path, key, params=None, soft=False):
    if api == "accounts":
        return ACCOUNTS
    return LOCATIONS[path.split("/locations")[0]]


class TempDbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for p in (mock.patch.object(storage, "DATA", self.tmp.name),
                  mock.patch.object(storage, "DB", os.path.join(self.tmp.name, "t.db")),
                  mock.patch.object(storage, "EX_CLIENTES", {"locations/99999999999999999999"})):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.db = storage.connect()
        self.addCleanup(self.db.close)


class SyncLocationsTest(TempDbCase):
    def run_sync(self, on_progress=None):
        with mock.patch.object(service.g, "paginate", fake_paginate):
            return service.sync_locations(self.db, on_progress)

    def test_grava_locais_e_conta(self):
        r = self.run_sync()
        self.assertEqual((r.found, r.new, r.accounts, r.total), (3, 3, 2, 3))
        row = storage.find_location(self.db, "Clinica Tres")
        self.assertEqual((row["account_id"], row["account_name"]), ("accounts/2", "Conta B"))

    def test_ex_cliente_conhecido_entra_inativo_e_flag_e_mantida(self):
        self.run_sync()
        active = {r["id"]: r["active"] for r in storage.list_locations(self.db)}
        self.assertEqual(active["locations/99999999999999999999"], 0)
        storage.set_active(self.db, "locations/1", False)
        self.db.commit()
        r = self.run_sync()  # segunda vez: nada novo e o 'active' escolhido continua
        self.assertEqual(r.new, 0)
        self.assertEqual(storage.find_location(self.db, "locations/1")["active"], 0)

    def test_progresso_por_conta(self):
        events = []
        self.run_sync(events.append)
        self.assertEqual([(e["accounts_done"], e["accounts_total"], e["locations_found"]) for e in events],
                         [(0, 2, 0), (1, 2, 2), (2, 2, 3)])

    def test_erro_da_api_vira_sync_error(self):
        with mock.patch.object(service.g, "paginate", side_effect=SystemExit("HTTP 403: sem permissão")):
            with self.assertRaisesRegex(service.SyncError, "HTTP 403"):
                service.sync_locations(self.db)

    def test_erro_de_rede_vira_sync_error(self):
        with mock.patch.object(service.g, "paginate", side_effect=requests.ConnectionError()):
            with self.assertRaisesRegex(service.SyncError, "Sem conexao"):
                service.sync_locations(self.db)


def wait_until_finished(job, timeout=5):
    end = time.time() + timeout
    while job.state()["status"] == "running" and time.time() < end:
        time.sleep(0.01)
    return job.state()


class SyncJobTest(TempDbCase):
    def test_conclui_com_resultado(self):
        job = service.SyncJob()
        with mock.patch.object(service.g, "paginate", fake_paginate):
            self.assertTrue(job.start())
            state = wait_until_finished(job)
        self.assertEqual((state["status"], state["total"], state["new"]), ("done", 3, 3))

    def test_nao_inicia_duas_vezes(self):
        job = service.SyncJob()
        gate = __import__("threading").Event()
        with mock.patch.object(service, "sync_locations", lambda db, cb: gate.wait(5) or service.SyncResult(0, 0, 0, 0)):
            self.assertTrue(job.start())
            self.assertFalse(job.start())
            gate.set()
            wait_until_finished(job)

    def test_erro_fica_no_estado(self):
        job = service.SyncJob()
        with mock.patch.object(service.g, "paginate", side_effect=SystemExit("HTTP 401")):
            job.start()
            state = wait_until_finished(job)
        self.assertEqual(state["status"], "error")
        self.assertIn("HTTP 401", state["message"])

    def test_excecao_inesperada_nao_deixa_preso_em_running(self):
        job = service.SyncJob()
        with mock.patch.object(service, "sync_locations", side_effect=ValueError("x")):
            job.start()
            state = wait_until_finished(job)
        self.assertEqual(state["status"], "error")


class SyncWebTest(TempDbCase):
    def setUp(self):
        super().setUp()
        self.job = service.SyncJob()
        p = mock.patch.object(webapp, "sync_job", self.job)
        p.start()
        self.addCleanup(p.stop)
        self.client = TestClient(webapp.app, base_url="http://127.0.0.1:8000")

    def test_tela_tem_o_botao(self):
        html = self.client.get("/").text
        self.assertIn("Sincronizar locais", html)
        self.assertIn('hx-post="/sincronizar"', html)

    def test_post_inicia_e_devolve_andamento_com_polling(self):
        gate = __import__("threading").Event()
        with mock.patch.object(service, "sync_locations", lambda db, cb: (cb({"accounts_total": 2, "accounts_done": 1,
                               "locations_found": 7, "account_name": "x"}), gate.wait(5), service.SyncResult(7, 1, 2, 7))[2]):
            html = self.client.post("/sincronizar").text
            self.assertIn('hx-get="/sincronizar/status"', html)
            self.assertIn("disabled", html)
            # Aguarda o primeiro progresso e confere o texto.
            for _ in range(200):
                status = self.client.get("/sincronizar/status").text
                if "Conta 2 de 2" in status:
                    break
                time.sleep(0.01)
            self.assertIn("Conta 2 de 2: buscando locais (7 até agora)", status)
            self.assertIn("<progress", status)
            gate.set()
            wait_until_finished(self.job)

    def test_conclusao_avisa_e_dispara_atualizacao_do_seletor(self):
        with mock.patch.object(service.g, "paginate", fake_paginate):
            self.client.post("/sincronizar")
            wait_until_finished(self.job)
        r = self.client.get("/sincronizar/status")
        self.assertEqual(r.headers.get("HX-Trigger"), "syncDone")
        self.assertIn("Sincronizado: 3 locais (3 novos)", r.text)
        self.assertNotIn("hx-trigger=\"every 1s\"", r.text)  # para de consultar
        picker = self.client.get("/seletor").text
        self.assertIn("Clinica Um", picker)
        self.assertNotIn("Salao Antigo", picker)  # ex-cliente segue inativo

    def test_erro_aparece_como_alerta(self):
        with mock.patch.object(service.g, "paginate", side_effect=SystemExit("HTTP 403: sem permissão")):
            self.client.post("/sincronizar")
            wait_until_finished(self.job)
        r = self.client.get("/sincronizar/status")
        self.assertIn('role="alert"', r.text)
        self.assertIn("HTTP 403: sem permissão", r.text)
        self.assertIsNone(r.headers.get("HX-Trigger"))

    def test_pagina_nova_nao_repete_mensagem_antiga(self):
        with mock.patch.object(service.g, "paginate", fake_paginate):
            self.client.post("/sincronizar")
            wait_until_finished(self.job)
        self.assertNotIn("Sincronizado:", self.client.get("/").text)

    def test_post_de_outro_site_e_recusado(self):
        r = self.client.post("/sincronizar", headers={"origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.job.state()["status"], "idle")

    def test_estado_vazio_atualiza_a_pagina_ao_sincronizar(self):
        html = self.client.get("/").text  # banco sem locais
        self.assertIn("Nenhum local ativo", html)
        self.assertIn('hx-trigger="syncDone from:body"', html)


if __name__ == "__main__":
    unittest.main()
