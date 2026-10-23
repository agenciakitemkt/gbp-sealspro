import unittest

from scoring.items.reviews_count import ITEM
from tests.scoring.helpers import review, run, referencia


def with_n(n):
    p = referencia()
    p["reviews"] = [review() for _ in range(n)]
    return run(ITEM, p)


class ReviewsCountTest(unittest.TestCase):
    def test_muitas(self):  # medido: 21 = 100
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_poucas(self):
        self.assertEqual(with_n(3).score, 100)
        self.assertEqual(with_n(2).score, 66)
        self.assertEqual(with_n(0).score, 0)


if __name__ == "__main__":
    unittest.main()
