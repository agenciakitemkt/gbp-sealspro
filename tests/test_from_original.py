"""Adaptador do `pd` do GBP Check original para o perfil normalizado da Pre Analise (dados sinteticos)."""

import copy
import unittest
from datetime import datetime, timezone

from collector_pre.from_original import analyzed_at, to_profile

PD = {
    "cid": "123", "place_id": "ChIJ-exemplo", "location_name": "Negócio Exemplo", "category": "Oftalmologista",
    "all_categories": ["Ophthalmologist"], "address": "Rua Exemplo, 100", "address_info": {"city": "Cidade Exemplo"},
    "phones": ["+55 00 0000-0000", "+55 00 1111-1111"], "website": "https://example.com/",
    "description": "Texto", "hours": {"Monday": "8 AM–6 PM"}, "logo_url": "https://example.com/l.jpg",
    "cover_photo_url": None, "is_verified": True,
    "social_links": [{"name": "Instagram", "url": "https://www.instagram.com/exemplo/"}],
    "reviews_qty": 88, "reviews_average": 4.9, "reviews_by_stars": [1, 0, 0, 3, 84], "last_review_days_ago": 7,
    "reviews_statistics": {"total_reviews": 35, "not_answered": 3, "reviews_with_text": 21, "avg_rating": 4.92,
                           "last_fixed_n": 5, "last_fixed_statistics": {"total_reviews": 5, "avg_rating": 5}},
    "media_statistics": {"last_media_days_since": 30, "video_count": 2, "image_360_count": 1, "total_items": 12},
    "total_photos": 15, "posts_count": 3, "last_post_days_ago": 21,
    "avg_reviews_count_all": 181, "is_location_on_top_10": False,
}
CASE = {"id": "019f445d-c9ca-7000-8000-000000000000", "ncomp": 120, "pd": PD}


def case(**pd_changes):
    c = copy.deepcopy(CASE)
    c["pd"].update(pd_changes)
    return c


class PerfilTest(unittest.TestCase):
    def test_campos_do_perfil(self):
        loc = to_profile(CASE)["location"]
        self.assertEqual(loc["name"], "Negócio Exemplo")
        self.assertEqual(loc["phone"], "+55 00 0000-0000")  # o primeiro telefone
        self.assertEqual(loc["city"], "Cidade Exemplo")
        self.assertEqual(loc["coverUrl"], "")
        self.assertTrue(loc["verified"])
        self.assertEqual(loc["socialLinks"], [{"name": "Instagram", "url": "https://www.instagram.com/exemplo/"}])

    def test_avaliacoes_e_amostra(self):
        r = to_profile(CASE)["reviews"]
        self.assertEqual((r["count"], r["average"], r["lastReviewDays"]), (88, 4.9, 7))
        self.assertEqual(r["starDistribution"], [84, 3, 0, 0, 1])  # o original manda de 1 a 5 estrelas
        self.assertEqual(r["sample"], {"size": 35, "unanswered": 3, "withText": 21, "average": 4.92,
                                       "recentSize": 5, "recentAverage": 5.0})

    def test_midia_postagens_e_concorrentes(self):
        p = to_profile(CASE)
        self.assertEqual(p["media"], {"lastOwnerPhotoDays": 30, "videos": 2, "photos360": 1, "total": 15})
        self.assertEqual(p["posts"], {"count": 3, "lastPostDays": 21})
        self.assertEqual(p["competitors"], {"count": 120, "averageReviews": 181, "inTop10ByReviews": False})

    def test_data_da_analise_vem_do_uuid7(self):
        self.assertEqual(analyzed_at(CASE["id"]), datetime(2026, 7, 9, 0, 53, 45, 34000, tzinfo=timezone.utc))
        self.assertTrue(to_profile(CASE)["collectedAt"].startswith("2026-07-09T00:53:45"))
        self.assertIsNone(analyzed_at("nao-e-uuid"))


class SemDadoTest(unittest.TestCase):
    def test_quantidade_vazia_vira_zero_avaliacoes(self):
        for empty in (None, ""):
            r = to_profile(case(reviews_qty=empty, reviews_average=empty, reviews_by_stars=[0, 0, 0, 0, 0]))["reviews"]
            self.assertEqual((r["count"], r["average"]), (0, None))

    def test_grupos_sem_dado_viram_none(self):
        p = to_profile(case(reviews_statistics=None, media_statistics=None))
        self.assertIsNone(p["reviews"]["sample"])
        self.assertIsNone(p["media"])

    def test_sem_concorrentes(self):
        c = case(avg_reviews_count_all=0, is_location_on_top_10=True)
        c["ncomp"] = 0
        self.assertEqual(to_profile(c)["competitors"]["count"], 0)

    def test_aceita_so_o_pd(self):
        p = to_profile(copy.deepcopy(PD))
        self.assertEqual(p["location"]["name"], "Negócio Exemplo")
        self.assertEqual(p["competitors"]["count"], 0)  # sem ncomp


if __name__ == "__main__":
    unittest.main()
