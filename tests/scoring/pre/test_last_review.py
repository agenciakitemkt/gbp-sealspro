import unittest

from scoring.pre.items.last_review import ITEM
from tests.scoring.pre.helpers import score


def s(days):
    return score(ITEM, reviews__lastReviewDays=days)


class UltimaAvaliacaoTest(unittest.TestCase):
    def test_pontos_medidos(self):
        for days, expected in ((0, 100), (30, 100), (31, 50), (60, 0), (2190, 0)):
            self.assertEqual(s(days), expected, days)

    def test_limite_provavel(self):
        self.assertEqual(s(59), 50)

    def test_sem_avaliacao_e_0(self):
        self.assertEqual(s(None), 0)
        self.assertEqual(score(ITEM, reviews__count=0), 0)
