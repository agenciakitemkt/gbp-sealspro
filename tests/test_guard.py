import os
import tempfile
import unittest

from tests import guard


class GuardTest(unittest.TestCase):
    """Prova que a protecao funciona: ela precisa apontar cada tipo de mudanca."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "raw", "locations_1"))
        os.makedirs(os.path.join(self.root, "prints"))
        self.write("gbp.db", "banco")
        self.write("raw/locations_1/a.json", "{}")
        self.write("prints/tela.png", "img")

    def write(self, rel, content):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as f:
            f.write(content)

    def test_sem_mudanca_nao_aponta_nada(self):
        before = guard.snapshot(self.root)
        self.assertEqual(guard.diff(before, guard.snapshot(self.root)), [])

    def test_arquivo_alterado_no_banco(self):
        before = guard.snapshot(self.root)
        self.write("gbp.db", "banco mexido")
        self.assertEqual(guard.diff(before, guard.snapshot(self.root)), ["alterado: gbp.db"])

    def test_arquivo_novo_em_raw(self):
        before = guard.snapshot(self.root)
        os.makedirs(os.path.join(self.root, "raw", "locations_fake"))
        self.write("raw/locations_fake/b.json", "{}")
        self.assertEqual(guard.diff(before, guard.snapshot(self.root)), [f"novo: {os.path.join('raw', 'locations_fake', 'b.json')}"])

    def test_arquivo_removido_de_raw(self):
        before = guard.snapshot(self.root)
        os.remove(os.path.join(self.root, "raw", "locations_1", "a.json"))
        self.assertEqual(guard.diff(before, guard.snapshot(self.root)), [f"removido: {os.path.join('raw', 'locations_1', 'a.json')}"])

    def test_alteracao_de_um_byte_e_detectada(self):
        self.write("raw/locations_1/a.json", "{ }")
        before = guard.snapshot(self.root)
        self.write("raw/locations_1/a.json", "{x}")
        self.assertEqual(len(guard.diff(before, guard.snapshot(self.root))), 1)

    def test_pasta_excluida_e_ignorada(self):
        before = guard.snapshot(self.root, exclude=("prints",))
        self.write("prints/outra.png", "x")
        self.assertEqual(guard.diff(before, guard.snapshot(self.root, exclude=("prints",))), [])
        self.assertNotEqual(guard.diff(guard.snapshot(self.root), before), [])  # sem exclude, aparece

    def test_pasta_inexistente(self):
        self.assertEqual(guard.snapshot(os.path.join(self.root, "nao-existe")), {})

    def test_o_pacote_de_testes_isola_o_storage_por_padrao(self):
        import storage
        self.assertTrue(storage.DATA.startswith(tempfile.gettempdir()) or "gbp-testes-" in storage.DATA)
        self.assertNotEqual(os.path.realpath(storage.DATA), os.path.realpath(guard.REAL_DATA))

    def test_sem_isolamento_um_teste_poluiria_e_a_protecao_acusaria(self):
        """Simula o incidente: um teste que grava no 'data' real. O diff acusa o arquivo falso."""
        before = guard.snapshot(self.root)
        fake_dir = os.path.join(self.root, "raw", "locations_1")
        self.write("raw/locations_1/20261008T214544Z.json", '{"info": {"title": "Clinica X"}}')
        changes = guard.diff(before, guard.snapshot(self.root))
        self.assertEqual(len(changes), 1)
        self.assertTrue(changes[0].startswith("novo: raw"))
        self.assertTrue(os.path.isdir(fake_dir))


if __name__ == "__main__":
    unittest.main()
