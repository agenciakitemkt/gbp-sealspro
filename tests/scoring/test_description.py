import unittest

from scoring.items.description import ITEM
from tests.scoring.helpers import run, referencia


def with_size(n):
    p = referencia()
    p["location"]["description"] = "x" * n
    return run(ITEM, p)


class DescriptionTest(unittest.TestCase):
    def test_585_caracteres_e_bom(self):  # medido no original
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_minimo_exato(self):
        self.assertEqual(with_size(50).score, 100)

    def test_abaixo_do_minimo_e_proporcional(self):  # hipótese: atual/recomendado
        self.assertEqual(with_size(49).score, 98)
        self.assertEqual(with_size(25).score, 50)
        self.assertEqual(with_size(0).score, 0)

    def test_espacos_nao_contam(self):
        p = referencia()
        p["location"]["description"] = "   "
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
