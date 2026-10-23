import unittest

from scoring.pre.items.last_post import ITEM
from tests.scoring.pre.helpers import score


def s(days):
    return score(ITEM, posts__lastPostDays=days)


class UltimaPostagemTest(unittest.TestCase):
    def test_pontos_medidos(self):
        for days, expected in ((0, 100), (8, 100), (21, 50), (74, 0), (119, 0)):
            self.assertEqual(s(days), expected, days)

    def test_limites_da_regra_provavel(self):
        self.assertEqual([s(d) for d in (15, 16, 30, 31)], [100, 50, 50, 0])

    def test_sem_postagem_e_0(self):
        self.assertEqual(score(ITEM, posts__count=0, posts__lastPostDays=None), 0)
        self.assertEqual(score(ITEM, posts__lastPostDays=None), 0)
