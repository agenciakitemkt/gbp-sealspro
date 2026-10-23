import unittest

from scoring.pre.items.social_links import ITEM
from tests.scoring.pre.helpers import run, profile, score


class RedesSociaisTest(unittest.TestCase):
    def test_uma_ou_mais_e_100(self):
        self.assertEqual(score(ITEM), 100)

    def test_nenhuma_e_50_e_nao_0(self):
        self.assertEqual(score(ITEM, location__socialLinks=[]), 50)

    def test_vars(self):
        links = [{"name": "Instagram", "url": "a"}, {"name": "Facebook", "url": "b"}]
        self.assertEqual(run(ITEM, profile(location__socialLinks=links)).vars,
                         {"current": 2, "names": "Instagram, Facebook"})
