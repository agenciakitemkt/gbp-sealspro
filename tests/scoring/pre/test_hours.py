import unittest

from scoring.pre.items.hours import ITEM
from tests.scoring.pre.helpers import score


class HorarioTest(unittest.TestCase):
    def test_definido_e_nao(self):
        self.assertEqual(score(ITEM), 100)
        self.assertEqual(score(ITEM, location__hours={}), 0)
        self.assertEqual(score(ITEM, location__hours=None), 0)
