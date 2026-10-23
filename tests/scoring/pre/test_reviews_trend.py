import unittest

from scoring.pre.items.reviews_trend import ITEM
from scoring.pre.base import recent_window
from tests.scoring.pre.helpers import profile, run, score


def s(recent, average):
    return score(ITEM, reviews__sample__recentAverage=recent, reviews__sample__average=average)


class TendenciaTest(unittest.TestCase):
    def test_pontos_medidos(self):
        self.assertEqual(s(3.4, 4.47), 0)    # queda de 1,07
        self.assertEqual(s(4.2, 4.81), 0)    # queda de 0,61
        self.assertEqual(s(4.5, 4.93), 100)  # queda de 0,43
        self.assertEqual(s(4.69, 4.4), 100)  # alta

    def test_corte_hipotese_de_meio_ponto(self):
        self.assertEqual(s(4.5, 5.0), 100)
        self.assertEqual(s(4.49, 5.0), 0)

    def test_n_e_10_por_cento_do_total_com_minimo_5(self):  # medido nos 47 casos com amostra
        ratings = [5] * 12 + [1] * 88
        self.assertEqual(recent_window(profile(reviews__count=120, reviews__sample__ratings=ratings))[0], 12)
        self.assertEqual(recent_window(profile(reviews__count=441, reviews__sample__ratings=ratings))[0], 44)
        self.assertEqual(recent_window(profile(reviews__count=30, reviews__sample__ratings=ratings))[0], 5)

    def test_n_maior_que_a_amostra_usa_a_amostra_inteira(self):
        ratings = [5, 4, 3]
        self.assertEqual(recent_window(profile(reviews__count=1360, reviews__sample__ratings=ratings)), (3, 4.0, 4.0))

    def test_calcula_pelas_notas_quando_ha_ratings(self):
        # 5 mais recentes com 3 estrelas, resto 5: media recente 3,0 contra 4,8 da amostra = queda de 1,8
        ratings = [3] * 5 + [5] * 45
        p = profile(reviews__count=40, reviews__sample__ratings=ratings)
        self.assertEqual(run(ITEM, p).score, 0)
        self.assertEqual(run(ITEM, p).vars, {"recent": 3.0, "recentSize": 5, "average": 4.8, "size": 40})

    def test_sem_ratings_usa_o_calculo_do_original(self):
        self.assertEqual(recent_window(profile()), (5, 5.0, 4.9))

    def test_depende_da_amostra(self):
        self.assertEqual(ITEM.requires, ("review_sample",))
