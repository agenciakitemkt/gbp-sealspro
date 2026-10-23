"""Contrato do diagnostico com ferramentas externas (skill que aplica as mudancas). Se um destes testes falhar por mudanca de
formato, subir diagnostico.CONTRATO e atualizar a skill do outro lado (CLAUDE.md, secao 15)."""

import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import coletar
import diagnostico
import storage
from collector.normalize import normalize
from scoring import analyze
from tests.test_history import TempStorage
from tests.test_report import REVIEW_TEXT, make_raw

CHAVES = {"contrato", "local", "analise", "perfil", "itens"}
CHAVES_ITEM = {"id", "titulo", "status", "nota", "precisaAcao", "situacao", "orientacao", "dados", "comoResolver",
               "campoApi", "cuidado"}
CHAVES_PERFIL = {"nome", "categoria", "categoriasAdicionais", "endereco", "cidade", "telefone", "site", "descricao",
                 "horario", "horarioEspecial", "servicos", "aceitaServicos", "dataFundacao", "mapsUrl",
                 "temLogotipo", "temCapa"}


class DiagnosticoTest(TempStorage):
    def test_formato_do_contrato(self):
        self.analysis(make_raw())
        d = diagnostico.build(self.db, "locations/1")
        self.assertEqual(d["contrato"], 1)
        self.assertEqual(set(d), CHAVES)
        self.assertEqual(set(d["perfil"]), CHAVES_PERFIL)
        self.assertEqual(set(d["analise"]), {"id", "data", "nota", "bom", "razoavel", "fraco", "indisponiveis"})
        self.assertEqual(len(d["itens"]), 21)
        for item in d["itens"]:
            self.assertEqual(set(item), CHAVES_ITEM)
            self.assertIn(item["comoResolver"], {"texto", "material", "postagem", "resposta", "cliente"})

    def test_todo_item_do_motor_tem_forma_de_resolver(self):
        ids = {i["id"] for i in analyze(normalize(make_raw()))["items"]}
        self.assertEqual(ids, set(diagnostico.COMO_RESOLVER))
        self.assertTrue(set(diagnostico.CAMPO_API) <= ids)

    def test_precisa_acao_so_para_fraco_e_razoavel_com_situacao_e_orientacao(self):
        self.analysis(make_raw())
        for item in diagnostico.build(self.db, "locations/1")["itens"]:
            self.assertEqual(item["precisaAcao"], item["status"] in ("fair", "bad"))
            if item["status"] in ("good", "fair", "bad"):
                self.assertTrue(item["situacao"] and item["orientacao"], item["id"])

    def test_nome_do_negocio_tem_aviso_de_cuidado(self):
        self.analysis(make_raw())
        item = next(i for i in diagnostico.build(self.db, "locations/1")["itens"] if i["id"] == "business_name")
        self.assertIn("verificação", item["cuidado"])

    def test_recalcula_com_o_motor_atual(self):
        self.analysis(make_raw(), engine_version="0", config_hash="z" * 64)
        d = diagnostico.build(self.db, "locations/1")
        self.assertEqual(d["analise"]["nota"], analyze(normalize({**make_raw(), "location": "locations/1"}))["overall"]["score"])

    def test_nunca_traz_texto_de_avaliacao(self):
        self.analysis(make_raw())
        self.assertNotIn(REVIEW_TEXT, json.dumps(diagnostico.build(self.db, "locations/1"), ensure_ascii=False))

    def test_sem_analise_real(self):
        self.analysis(make_raw(), kind="retroativa")
        with self.assertRaisesRegex(LookupError, "análise real"):
            diagnostico.build(self.db, "locations/1")

    def test_sem_bruto_usa_a_guardada_se_for_da_versao_atual(self):
        aid = self.analysis(make_raw())
        os.remove(storage.get_analysis(self.db, aid)["raw_path"])
        d = diagnostico.build(self.db, "locations/1")
        self.assertIsNone(d["perfil"])
        self.assertEqual(len(d["itens"]), 21)


class DiagnosticoCliTest(TempStorage):
    def run_cli(self, analisar=False):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            coletar.cmd_diagnostico(self.db, mock.Mock(alvo="Clinica X", analisar=analisar))
        return out.getvalue(), err.getvalue()

    def test_saida_padrao_e_so_o_json(self):
        self.analysis(make_raw())
        out, _ = self.run_cli()
        self.assertEqual(json.loads(out)["local"]["id"], "locations/1")

    def test_analisar_faz_analise_real_antes(self):
        def fake_run(db, location):
            self.analysis(make_raw("2026-10-10T12:00:00+00:00"))
        with mock.patch.object(coletar, "run_analysis", side_effect=fake_run) as run:
            out, err = self.run_cli(analisar=True)
        run.assert_called_once()
        self.assertTrue(json.loads(out)["analise"]["data"].startswith("2026-10-10"))
        self.assertIn("Analise real nova", err)

    def test_sem_analise_sai_com_mensagem(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli()
        self.assertIn("análise real", str(ctx.exception))
