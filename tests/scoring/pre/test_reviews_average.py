import unittest

from scoring.pre.items.reviews_average import ITEM
from tests.scoring.pre.helpers import score


def s(avg):
    return score(ITEM, reviews__average=avg)


class MediaTest(unittest.TestCase):
    def test_pontos_medidos(self):
        for avg, expected in ((1.0, 0), (3.7, 50), (4.1, 50), (4.3, 50), (4.5, 100), (4.9, 100), (5.0, 100)):
            self.assertEqual(s(avg), expected, avg)

    def test_hipoteses(self):
        self.assertEqual(s(4.4), 50)
        self.assertEqual(s(3.5), 50)
        self.assertEqual(s(3.4), 0)

    def test_sem_avaliacao_e_0(self):
        self.assertEqual(score(ITEM, reviews__count=0, reviews__average=None), 0)
        self.assertEqual(score(ITEM, reviews__average=None), 0)
