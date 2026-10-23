import unittest

from scoring.items.last_owner_media import ITEM
from tests.scoring.helpers import days_ago, media, run, referencia


def with_days(*ages):
    p = referencia()
    p["media"] = [media(created=days_ago(a)) for a in ages]
    return run(ITEM, p)


class LastOwnerMediaTest(unittest.TestCase):
    def test_referencia_midia_recente(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_zero_dias_e_100(self):  # medido
        self.assertEqual(with_days(0).score, 100)

    def test_pontos_medidos_na_completa(self):  # dias -> nota do original
        for days, expected in ((8, 100), (23, 100), (28, 100), (57, 100), (86, 50), (152, 0), (153, 0)):
            self.assertEqual(with_days(days).score, expected, days)

    def test_degraus_hipoteticos(self):  # 100 até 59, 50 de 60 a 119, 0 de 120 em diante
        for days, expected in ((59, 100), (60, 50), (119, 50), (120, 0), (400, 0)):
            self.assertEqual(with_days(days).score, expected, days)

    def test_data_1970_e_ignorada(self):
        p = referencia()
        p["media"] = [media(created="1970-01-01T00:00:00Z")]
        self.assertEqual(run(ITEM, p).score, 0)
        p["media"].append(media(created=days_ago(60)))
        self.assertEqual(run(ITEM, p).score, 50)

    def test_sem_midia(self):
        self.assertEqual(with_days().score, 0)


if __name__ == "__main__":
    unittest.main()
