import unittest

from scoring.items.reviews_average import ITEM
from tests.scoring.helpers import review, run, referencia


def with_rating(r):
    p = referencia()
    p["location"]["rating"] = r
    return run(ITEM, p)


class ReviewsAverageTest(unittest.TestCase):
    def test_cinco_estrelas_e_bom(self):  # medido
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_curva_hipotetica(self):
        self.assertEqual(with_rating(4.5).score, 100)
        self.assertEqual(with_rating(4.0).score, 75)
        self.assertEqual(with_rating(3.0).score, 25)
        self.assertEqual(with_rating(1.5).score, 12)

    def test_quase_bom_nunca_da_100(self):
        self.assertEqual(with_rating(4.49).score, 99)

    def test_sem_avaliacoes(self):
        p = referencia()
        p["reviews"], p["location"]["rating"] = [], 0.0
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
