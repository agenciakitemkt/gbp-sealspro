import unittest

from scoring.pre.items.last_owner_photo import ITEM
from tests.scoring.pre.helpers import score


def s(days):
    return score(ITEM, media__lastOwnerPhotoDays=days)


class UltimaFotoTest(unittest.TestCase):
    def test_pontos_medidos(self):
        for days, expected in ((3, 100), (30, 100), (31, 50), (60, 50), (90, 0), (365, 0)):
            self.assertEqual(s(days), expected, days)

    def test_sem_foto_do_proprietario_e_0(self):
        self.assertEqual(s(None), 0)

    def test_depende_dos_dados_de_midia(self):
        self.assertEqual(ITEM.requires, ("media",))
