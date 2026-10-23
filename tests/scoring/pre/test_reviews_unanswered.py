import unittest

from scoring.pre.items.reviews_unanswered import ITEM
from tests.scoring.pre.helpers import run, profile, score


def s(unanswered, size):
    return score(ITEM, reviews__sample__unanswered=unanswered, reviews__sample__size=size)


class SemRespostaTest(unittest.TestCase):
    def test_pontos_medidos(self):
        for (u, n), expected in (((0, 10), 100), ((6, 88), 100), ((4, 38), 50), ((25, 50), 50),
                                 ((2, 3), 0), ((1, 1), 0)):
            self.assertEqual(s(u, n), expected, (u, n))

    def test_limites_da_regra_provavel(self):
        self.assertEqual([s(9, 100), s(10, 100), s(50, 100), s(51, 100)], [100, 50, 50, 0])

    def test_vars(self):
        self.assertEqual(run(ITEM, profile(reviews__sample__unanswered=6, reviews__sample__size=88)).vars,
                         {"current": 6, "size": 88, "percent": 6.8, "recommended": 10})
