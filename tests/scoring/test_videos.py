import unittest

from scoring.items.videos import ITEM
from tests.scoring.helpers import media, run, referencia


def with_videos(n):
    p = referencia()
    p["media"] = [m for m in p["media"] if m["format"] != "VIDEO"] + [media("VIDEO") for _ in range(n)]
    return run(ITEM, p)


class VideosTest(unittest.TestCase):
    def test_referencia_dois_videos_da_66(self):  # ponto medido: 2 de 3 = 66
        out = run(ITEM, referencia())
        self.assertEqual((out.score, out.vars["current"]), (66, 2))

    def test_tres_ou_mais_e_bom(self):
        self.assertEqual(with_videos(3).score, 100)
        self.assertEqual(with_videos(10).score, 100)

    def test_menos_que_dois(self):  # medido: 0 = 0, 1 = 50
        self.assertEqual(with_videos(1).score, 50)
        self.assertEqual(with_videos(0).score, 0)

    def test_fotos_nao_contam(self):
        p = referencia()
        p["media"] = [media("PHOTO") for _ in range(5)]
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
