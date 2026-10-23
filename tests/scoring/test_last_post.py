import unittest

from scoring.items.last_post import ITEM
from tests.scoring.helpers import days_ago, run, referencia


def with_days(*ages):
    p = referencia()
    p["posts"] = [{"type": "STANDARD", "createdAt": days_ago(a)} for a in ages]
    return run(ITEM, p)


class LastPostTest(unittest.TestCase):
    def test_referencia_postagem_recente(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_100_ate_30_dias_e_0_acima(self):  # hipótese (degrau) a partir dos pontos medidos
        self.assertEqual(with_days(30).score, 100)
        self.assertEqual(with_days(31).score, 0)

    def test_pontos_medidos_na_completa(self):  # dias -> nota do original
        for days, expected in ((1, 100), (3, 100), (5, 100), (10, 100), (38, 0), (43, 0)):
            self.assertEqual(with_days(days).score, expected, days)

    def test_usa_a_mais_recente(self):
        out = with_days(90, 5, 400)
        self.assertEqual((out.score, out.vars["current"]), (100, 5))

    def test_sem_postagens(self):
        self.assertEqual(with_days().score, 0)


if __name__ == "__main__":
    unittest.main()
