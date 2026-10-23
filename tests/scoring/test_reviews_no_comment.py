import unittest

from scoring.items.reviews_no_comment import ITEM
from tests.scoring.helpers import review, run, referencia


def with_share(without, total):
    p = referencia()
    p["reviews"] = [review(comment=i >= without) for i in range(total)]
    return run(ITEM, p)


class ReviewsNoCommentTest(unittest.TestCase):
    def test_referencia_27_por_cento_e_bom(self):  # medido: 6 de 22 = 27% -> 100
        out = run(ITEM, referencia())
        self.assertEqual((out.score, out.vars["percent"]), (100, 27))

    def test_44_por_cento_da_nota_50(self):  # medido na Pré Análise: 44% = 50
        out = with_share(11, 25)
        self.assertEqual((out.vars["percent"], out.score), (44, 50))

    def test_interpola_a_partir_do_ponto_medido(self):
        self.assertEqual(with_share(18, 25).score, 25)  # 72%: entre (44, 50) e (100, 0)

    def test_pontos_medidos_na_completa_dao_100(self):  # 35,7% (5 de 14) e 38,6% (27 de 70)
        self.assertEqual(with_share(5, 14).score, 100)
        self.assertEqual(with_share(27, 70).score, 100)

    def test_limite_do_bom_e_hipotese_de_40_por_cento(self):
        from scoring import config
        c = config.CONFIG["reviews_no_comment"]
        self.assertEqual((c["good_max_pct"], c["estado"]), (40, config.HIPOTESE))
        self.assertTrue(38.6 < c["good_max_pct"] < 44)  # acima do maior "bom" medido e abaixo do ponto de 50
        self.assertEqual(with_share(2, 5).score, 100)   # 40% ainda e bom
        self.assertTrue(50 < with_share(21, 50).score < 100)  # 42%: entre o limite e (44%, 50)

    def test_todas_sem_comentario(self):
        self.assertEqual(with_share(5, 5).score, 0)

    def test_nenhuma_sem_comentario(self):
        self.assertEqual(with_share(0, 5).score, 100)

    def test_sem_avaliacoes(self):
        p = referencia()
        p["reviews"] = []
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
