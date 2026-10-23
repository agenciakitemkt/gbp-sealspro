"""Roda por ultimo (ordem alfabetica): falha se algum teste mexeu nos dados reais em data/."""

import os
import unittest

import storage
from tests import REAL_DATA_AT_START, guard


class DadosReaisIntactosTest(unittest.TestCase):
    def test_nenhum_arquivo_de_data_mudou_durante_a_suite(self):
        changes = guard.diff(REAL_DATA_AT_START, guard.snapshot(guard.REAL_DATA, exclude=("prints",)))
        self.assertEqual(
            changes, [],
            "A suite mexeu em data/ (raw, gbp.db, backups ou reference). Algum teste esta usando o armazenamento "
            "real sem isolar. Se o app estava em uso ao mesmo tempo (Analisar ou Sincronizar), rode a suite de novo.")

    def test_por_padrao_o_armazenamento_dos_testes_nao_e_o_real(self):
        self.assertNotEqual(os.path.realpath(storage.DATA), os.path.realpath(guard.REAL_DATA))
        self.assertNotEqual(os.path.realpath(storage.DB), os.path.realpath(os.path.join(guard.REAL_DATA, "gbp.db")))

    def test_a_impressao_inicial_cobre_banco_e_brutos(self):  # a protecao nao pode ser vazia por engano
        if os.path.isdir(guard.REAL_DATA):
            self.assertTrue(any(p == "gbp.db" or p.startswith("raw") for p in REAL_DATA_AT_START) or not os.listdir(guard.REAL_DATA))


if __name__ == "__main__":
    unittest.main()
