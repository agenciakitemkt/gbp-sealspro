import unittest

from scoring.pre.items.business_name import ITEM
from tests.scoring.pre.helpers import run, profile, score


class NomeTest(unittest.TestCase):
    def test_ate_98_caracteres_e_bom(self):
        self.assertEqual(score(ITEM, location__name="a" * 82), 100)   # medido
        self.assertEqual(score(ITEM, location__name="a" * 98), 100)   # limite da mensagem do original

    def test_acima_de_98_e_50(self):
        self.assertEqual(score(ITEM, location__name="a" * 99), 50)
        self.assertEqual(score(ITEM, location__name="a" * 102), 50)   # medido

    def test_vars(self):
        self.assertEqual(run(ITEM, profile(location__name="abc")).vars, {"current": 3, "recommended": 98})
