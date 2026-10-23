import unittest

from scoring.pre.items.top10_reviews import ITEM
from tests.scoring.pre.helpers import score


class Top10Test(unittest.TestCase):
    def test_no_top_10_e_fora(self):
        self.assertEqual(score(ITEM), 100)
        self.assertEqual(score(ITEM, competitors__inTop10ByReviews=False), 0)

    def test_depende_dos_concorrentes(self):
        self.assertEqual(ITEM.requires, ("competitors",))
