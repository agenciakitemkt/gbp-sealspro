import unittest

from scoring.items.total_media import ITEM
from tests.scoring.helpers import media, run, referencia


class TotalMediaTest(unittest.TestCase):
    def test_nove_e_bom(self):  # medido: 9 = 100 (8 do proprietário + 1 de cliente)
        out = run(ITEM, referencia())
        self.assertEqual((out.score, out.vars["current"]), (100, 9))

    def test_soma_proprietario_e_clientes(self):
        p = referencia()
        p["media"], p["customerMedia"] = [media()], [media()]
        self.assertEqual(run(ITEM, p).score, 66)

    def test_sem_nenhuma(self):
        p = referencia()
        p["media"], p["customerMedia"] = [], []
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
