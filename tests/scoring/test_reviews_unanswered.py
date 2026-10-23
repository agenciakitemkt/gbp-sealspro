import unittest

from scoring.items.reviews_unanswered import ITEM
from tests.scoring.helpers import review, run, referencia


class ReviewsUnansweredTest(unittest.TestCase):
    def test_todas_respondidas(self):  # medido
        out = run(ITEM, referencia())
        self.assertEqual((out.score, out.vars["current"]), (100, 0))

    def test_conta_pela_quantidade_e_nao_pela_proporcao(self):
        # 0 = 100, 1 = 66, 2 = 33, 3 ou mais = 0 (2 e 3 são hipótese; 0, 1, 4 e 8 foram medidos)
        for unanswered, expected in ((0, 100), (1, 66), (2, 33), (3, 0), (4, 0), (8, 0)):
            p = referencia()
            p["reviews"] = [review(replied=i >= unanswered) for i in range(25)]
            out = run(ITEM, p)
            self.assertEqual((out.score, out.vars["current"]), (expected, unanswered), unanswered)

    def test_pontos_medidos_no_original(self):  # (sem resposta, total) -> nota
        for unanswered, total, expected in ((0, 112, 100), (1, 25, 66), (4, 34, 0), (8, 25, 0)):
            p = referencia()
            p["reviews"] = [review(replied=i >= unanswered) for i in range(total)]
            self.assertEqual(run(ITEM, p).score, expected, (unanswered, total))

    def test_a_idade_da_avaliacao_nao_conta(self):  # 8 sem resposta com 0 a 3 dias deram 0 no original
        from tests.scoring.helpers import days_ago
        p = referencia()
        p["reviews"] = [review(replied=False, created=days_ago(i % 4)) for i in range(8)] + [review() for _ in range(17)]
        self.assertEqual(run(ITEM, p).score, 0)

    def test_sem_avaliacoes_nada_a_responder(self):
        p = referencia()
        p["reviews"] = []
        self.assertEqual(run(ITEM, p).score, 100)

    def test_uma_nao_respondida_entre_poucas_pesa_igual(self):  # por quantidade: 1 sem resposta = 66
        p = referencia()
        p["reviews"] = [review(), review(replied=False)]
        self.assertEqual(run(ITEM, p).score, 66)


if __name__ == "__main__":
    unittest.main()
