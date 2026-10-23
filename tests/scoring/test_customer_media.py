import unittest

from scoring.items.customer_media import ITEM
from tests.scoring.helpers import media, run, referencia


def with_n(n):
    p = referencia()
    p["customerMedia"] = [media() for _ in range(n)]
    return run(ITEM, p)


class CustomerMediaTest(unittest.TestCase):
    def test_referencia_uma_de_tres_da_50(self):  # ponto medido: 1 de 3 = 50
        out = run(ITEM, referencia())
        self.assertEqual((out.score, out.vars["current"], out.vars["recommended"]), (50, 1, 3))

    def test_dois_da_66(self):  # medido: 0 = 0, 1 = 50, 2 = 66, 3 ou mais = 100
        self.assertEqual(with_n(2).score, 66)

    def test_extremos(self):
        self.assertEqual(with_n(0).score, 0)
        self.assertEqual(with_n(3).score, 100)
        self.assertEqual(with_n(7).score, 100)


if __name__ == "__main__":
    unittest.main()
