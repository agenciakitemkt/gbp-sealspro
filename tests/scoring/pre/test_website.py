import unittest

from scoring.pre.items.website import ITEM, is_social
from tests.scoring.pre.helpers import score


class WebsiteTest(unittest.TestCase):
    def test_dominio_proprio_e_100(self):
        for url in ("https://example.com.br/", "http://www.example.com/", "https://nome.wixsite.com/site",
                    "https://exemplo.pages.net.br/", "example.com"):
            self.assertEqual(score(ITEM, location__website=url), 100, url)

    def test_rede_social_e_50(self):
        for url in ("https://www.instagram.com/exemplo/", "http://www.instagram.com.br/exemplo",
                    "https://instagram.com/exemplo?igshid=abc", "https://m.facebook.com/exemplo"):
            self.assertEqual(score(ITEM, location__website=url), 50, url)

    def test_sem_site_e_0(self):
        self.assertEqual(score(ITEM, location__website=""), 0)
        self.assertEqual(score(ITEM, location__website=None), 0)

    def test_nome_parecido_nao_e_rede_social(self):
        self.assertFalse(is_social("https://instagramavel.com.br/"))
        self.assertFalse(is_social("https://www.example.com/instagram"))
