import unittest

from scoring.items.reviews_trend import ITEM
from tests.scoring.helpers import days_ago, review, run, referencia


def build(recent, older):
    p = referencia()
    p["reviews"] = ([review(r, created=days_ago(10)) for r in recent]
                    + [review(r, created=days_ago(200)) for r in older])
    return run(ITEM, p)


class ReviewsTrendTest(unittest.TestCase):
    def test_aumentando(self):
        out = build([5, 5], [4, 4])
        self.assertEqual((out.vars["trend"], out.score), ("up", 100))

    def test_estavel(self):
        self.assertEqual(build([5, 4], [5, 4]).vars["trend"], "stable")
        self.assertEqual(build([5, 5], [5, 5, 5, 5, 5, 5, 4]).vars["trend"], "stable")  # delta 0,14

    def test_variacao_exatamente_no_limite_conta_como_mudanca(self):
        self.assertEqual(build([5, 5], [5, 5, 5, 5, 4]).vars["trend"], "up")  # delta 0,2

    def test_diminuindo_perde_pontos(self):
        out = build([3, 3], [5, 5])
        self.assertEqual((out.vars["trend"], out.score), ("down", 50))

    def test_dados_insuficientes_e_neutro(self):
        out = run(ITEM, referencia())  # todas as avaliações da Referencia são recentes
        self.assertEqual((out.vars["trend"], out.score), ("stable", 100))
        self.assertEqual(build([], [5]).vars["trend"], "stable")


if __name__ == "__main__":
    unittest.main()
