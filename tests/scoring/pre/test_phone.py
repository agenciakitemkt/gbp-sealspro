import unittest

from scoring.pre.items.phone import ITEM
from tests.scoring.pre.helpers import score


class TelefoneTest(unittest.TestCase):
    def test_tem_e_nao_tem(self):
        self.assertEqual(score(ITEM), 100)
        self.assertEqual(score(ITEM, location__phone=""), 0)
        self.assertEqual(score(ITEM, location__phone="   "), 0)
