import unittest

from scoring.items.owner_media import ITEM
from tests.scoring.helpers import media, run, referencia


def with_n(n):
    p = referencia()
    p["media"] = [media() for _ in range(n)]
    return run(ITEM, p)


class OwnerMediaTest(unittest.TestCase):
    def test_oito_e_bom(self):  # medido: 8 = 100
        out = run(ITEM, referencia())
        self.assertEqual((out.score, out.vars["current"]), (100, 8))

    def test_abaixo_do_minimo(self):  # sem ponto medido: proporção
        self.assertEqual(with_n(2).score, 66)
        self.assertEqual(with_n(1).score, 33)
        self.assertEqual(with_n(0).score, 0)

    def test_minimo(self):
        self.assertEqual(with_n(3).score, 100)


if __name__ == "__main__":
    unittest.main()
