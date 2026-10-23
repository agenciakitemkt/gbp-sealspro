import unittest

from scoring.pre.items.videos import ITEM
from tests.scoring.pre.helpers import run, profile, score


def s(n):
    return score(ITEM, media__videos=n)


class VideosTest(unittest.TestCase):
    def test_pontos_medidos(self):
        self.assertEqual([s(0), s(2), s(4)], [0, 50, 100])

    def test_hipoteses_1_e_3(self):
        self.assertEqual(s(1), 25)   # interpolacao entre 0 = 0 e 2 = 50, nao medido
        self.assertEqual(s(3), 100)  # minimo recomendado na mensagem do original, nao medido

    def test_difere_da_completa(self):
        self.assertEqual(s(2), 50)   # na Completa 2 videos dao 66

    def test_vars(self):
        self.assertEqual(run(ITEM, profile(media__videos=2)).vars, {"current": 2, "recommended": 3})
