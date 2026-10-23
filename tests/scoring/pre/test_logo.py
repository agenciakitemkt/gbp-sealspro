import unittest

from scoring.pre.items.logo import ITEM
from tests.scoring.pre.helpers import score


class LogoTest(unittest.TestCase):
    def test_tem_e_nao_tem(self):
        self.assertEqual(score(ITEM), 100)
        self.assertEqual(score(ITEM, location__logoUrl=""), 0)
