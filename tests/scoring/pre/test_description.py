import unittest

from scoring.pre.items.description import ITEM
from tests.scoring.pre.helpers import score


def s(n):
    return score(ITEM, location__description="x" * n)


class DescricaoTest(unittest.TestCase):
    def test_pontos_medidos(self):
        for n, expected in ((0, 0), (23, 40), (48, 40), (54, 70), (99, 70), (101, 80), (108, 80), (122, 100), (762, 100)):
            self.assertEqual(s(n), expected, n)

    def test_limites_da_regra_provavel(self):
        self.assertEqual([s(n) for n in (1, 49, 50, 100, 119, 120)], [40, 40, 70, 80, 80, 100])

    def test_espacos_nao_contam(self):
        self.assertEqual(score(ITEM, location__description="   "), 0)
