import unittest

from scoring.pre.items.verified import ITEM
from tests.scoring.pre.helpers import score


class VerificadoTest(unittest.TestCase):
    def test_verificado_e_nao(self):
        self.assertEqual(score(ITEM), 100)
        self.assertEqual(score(ITEM, location__verified=False), 0)
