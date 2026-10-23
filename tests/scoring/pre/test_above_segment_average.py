import unittest

from scoring.pre.items.above_segment_average import ITEM
from tests.scoring.pre.helpers import score


class MediaDoSegmentoTest(unittest.TestCase):
    def test_maior_ou_igual_a_media(self):
        self.assertEqual(score(ITEM, reviews__count=115, competitors__averageReviews=26), 100)
        self.assertEqual(score(ITEM, reviews__count=30, competitors__averageReviews=30), 100)
        self.assertEqual(score(ITEM, reviews__count=171, competitors__averageReviews=287), 0)

    def test_sem_avaliacoes(self):
        self.assertEqual(score(ITEM, reviews__count=0, competitors__averageReviews=5), 0)
