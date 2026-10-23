import unittest

from collector.normalize import normalize


def raw(**kw):
    base = {
        "collectedAt": "2026-10-08T12:00:00+00:00", "location": "locations/1", "account": "accounts/1",
        "info": {
            "title": "Clinica X",
            "storefrontAddress": {"locality": "Belo Horizonte", "administrativeArea": "MG",
                                  "addressLines": ["Rua A, 1"]},
            "phoneNumbers": {"primaryPhone": "(31) 1"},
            "categories": {"primaryCategory": {"displayName": "Oftalmologista"}},
            "regularHours": {"periods": [{"openDay": "MONDAY", "openTime": {"hours": 7},
                                          "closeDay": "MONDAY", "closeTime": {"hours": 16, "minutes": 30}}]},
            "specialHours": {"specialHourPeriods": [
                {"startDate": {"year": 2026, "month": 10, "day": 12},
                 "endDate": {"year": 2026, "month": 10, "day": 12}, "closed": True}]},
            "serviceItems": [{"freeFormServiceItem": {"label": {"displayName": "Consulta"}}}],
            "openInfo": {"openingDate": {"year": 2026, "month": 9, "day": 10}},
            "metadata": {"mapsUri": "https://maps.google.com/?cid=1"},
        },
        "reviews": [
            {"starRating": "FIVE", "comment": "otimo", "reviewReply": {"comment": "obrigado"},
             "createTime": "2026-09-01T00:00:00Z"},
            {"starRating": "FOUR", "createTime": "2026-09-02T00:00:00Z"},
        ],
        "reviewsSummary": {"averageRating": 4.5, "totalReviewCount": 2},
        "media": [
            {"mediaFormat": "PHOTO", "locationAssociation": {"category": "PROFILE"},
             "createTime": "1970-01-01T00:00:00Z", "googleUrl": "http://logo"},
            {"mediaFormat": "PHOTO", "locationAssociation": {"category": "COVER"},
             "createTime": "2026-09-30T00:00:00Z", "googleUrl": "http://capa"},
            {"mediaFormat": "VIDEO", "locationAssociation": {"category": "ADDITIONAL"},
             "createTime": "2026-09-30T00:00:00Z"},
        ],
        "mediaCustomers": [], "localPosts": [{"topicType": "STANDARD", "createTime": "2026-10-05T00:00:00Z"}],
        "errors": {},
    }
    base.update(kw)
    return base


class NormalizeTest(unittest.TestCase):
    def test_contrato_basico(self):
        loc = normalize(raw())["location"]
        self.assertEqual(loc["category"], "Oftalmologista")
        self.assertEqual(loc["hours"], {"MONDAY": [["07:00", "16:30"]]})
        self.assertEqual(loc["openingDate"], "2026-09-10")
        self.assertEqual(loc["services"], ["Consulta"])
        self.assertEqual(loc["logoUrl"], "http://logo")
        self.assertEqual(loc["coverUrl"], "http://capa")

    def test_servicos_editaveis_vem_da_metadata(self):
        loc = lambda r: normalize(r)["location"]["servicesEditable"]  # noqa: E731
        base = raw()
        self.assertFalse(loc(base))  # a API omite booleanos falsos: sem a chave = nao pode editar
        base["info"]["metadata"]["canModifyServiceList"] = True
        self.assertTrue(loc(base))
        del base["info"]["metadata"]
        self.assertIsNone(loc(base))  # sem metadata nao da para saber

    def test_avaliacoes_vem_da_lista(self):
        p = normalize(raw())
        self.assertEqual(p["location"]["reviewCount"], 2)
        self.assertEqual(p["location"]["rating"], 4.5)
        self.assertEqual(p["location"]["starDistribution"], [1, 1, 0, 0, 0])  # 5 a 1
        self.assertEqual([(r["hasComment"], r["replied"]) for r in p["reviews"]], [(True, True), (False, False)])
        self.assertTrue(p["reviewsComplete"])

    def test_lista_incompleta_e_sinalizada(self):
        r = raw(reviewsSummary={"totalReviewCount": 60})
        self.assertFalse(normalize(r)["reviewsComplete"])

    def test_sem_avaliacoes(self):
        loc = normalize(raw(reviews=[]))["location"]
        self.assertEqual((loc["rating"], loc["reviewCount"], loc["starDistribution"]), (0.0, 0, [0] * 5))

    def test_secao_que_falhou_nao_vira_zero_silencioso(self):
        p = normalize(raw(media=None, errors={"media": "HTTP 500"}))
        self.assertEqual(p["collectionErrors"], {"media": "HTTP 500"})
        self.assertEqual(p["media"], [])


if __name__ == "__main__":
    unittest.main()
