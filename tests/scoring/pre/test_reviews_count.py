import unittest

from scoring.pre.items.reviews_count import ITEM
from tests.scoring.pre.helpers import score


class QuantidadeTest(unittest.TestCase):
    def test_curva_medida(self):
        self.assertEqual([score(ITEM, reviews__count=n) for n in (0, 1, 2, 3, 350)], [0, 50, 66, 100, 100])

    def test_sem_contagem_vale_zero(self):
        self.assertEqual(score(ITEM, reviews__count=None), 0)
