import unittest

from scoring.pre.items.reviews_with_text import ITEM
from tests.scoring.pre.helpers import score


def s(with_text, size):
    return score(ITEM, reviews__sample__withText=with_text, reviews__sample__size=size)


class SemComentarioTest(unittest.TestCase):
    def test_pontos_medidos(self):
        for (t, n), expected in (((19, 27), 100), ((71, 88), 100), ((9, 21), 50), ((2, 3), 50),
                                 ((5, 21), 0), ((0, 35), 0)):
            self.assertEqual(s(t, n), expected, (t, n))

    def test_limites(self):
        self.assertEqual([s(70, 100), s(69, 100), s(40, 100), s(39, 100)], [100, 50, 50, 0])
