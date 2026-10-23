import unittest

from scoring.pre.items.photos_360 import ITEM
from tests.scoring.pre.helpers import score


class Fotos360Test(unittest.TestCase):
    def test_pontos_medidos(self):
        self.assertEqual(score(ITEM, media__photos360=0), 0)
        self.assertEqual(score(ITEM, media__photos360=1), 0)    # 25 casos no original
        self.assertEqual(score(ITEM, media__photos360=2), 100)

    def test_depende_dos_dados_de_midia(self):
        self.assertEqual(ITEM.requires, ("media",))
