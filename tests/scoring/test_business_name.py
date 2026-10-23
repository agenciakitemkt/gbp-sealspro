import unittest

from scoring.items.business_name import ITEM
from tests.scoring.helpers import run, referencia


def with_name(n):
    p = referencia()
    p["location"]["name"] = "n" * n
    return run(ITEM, p).score


class BusinessNameTest(unittest.TestCase):
    def test_nome_curto_e_bom(self):  # medido: 34 = 100
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_limite(self):
        self.assertEqual(with_name(98), 100)
        self.assertEqual(with_name(99), 0)

    def test_vazio(self):
        self.assertEqual(with_name(0), 0)


if __name__ == "__main__":
    unittest.main()
