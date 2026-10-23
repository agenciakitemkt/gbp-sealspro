import glob
import json
import os
import re
import unittest

from collector_pre.from_original import to_profile
from scoring.base import status_for
from scoring.pre import analyze
from scoring.pre.items import ITEMS
from tests.scoring.pre.helpers import profile

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fixtures", "pre")
CATALOGO = ["location_name", "phone", "website", "hours", "description", "logo", "is_verified", "social_links",
            "posts", "media_freshness", "videos", "360_images", "reviews_quantity", "reviews_average",
            "last_review_date", "review_growth_trend", "reviews_without_response", "reviews_without_text",
            "reviews_ranking_top_10", "reviews_ranking_average"]


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def by_id(result):
    return {i["id"]: i for i in result["items"]}


class CasosReaisTest(unittest.TestCase):
    """Tres pre analises reais do original, anonimizadas (20, 17 e 14 itens): o motor, alimentado com os dados
    brutos via adaptador, reproduz nota geral, contadores e a nota de cada item."""

    def check(self, name, evaluated):
        case = fixture(name)
        result = analyze(to_profile(case))
        st, o = case["stats"], result["overall"]
        self.assertEqual((o["score"], o["good"], o["fair"], o["bad"]),
                         (st["overall_score"], st["good_items"], st["fair_items"], st["bad_items"]))
        self.assertEqual(o["good"] + o["fair"] + o["bad"], evaluated)
        self.assertEqual(o["unavailable"], 20 - evaluated)
        ours = {i["originalId"]: i["score"] for i in result["items"] if i["score"] is not None}
        self.assertEqual(ours, {i["id"]: i["s"] for i in case["items"]})

    def test_20_itens(self):
        self.check("caso_20_itens.json", 20)   # 75: 13 bons, 4 razoaveis, 3 fracos

    def test_17_itens(self):
        self.check("caso_17_itens.json", 17)   # 67: 11 bons, 1 razoavel, 5 fracos (sem midia)

    def test_14_itens(self):
        self.check("caso_14_itens.json", 14)   # 25: 3 bons, 1 razoavel, 10 fracos (sem midia e sem amostra)

    def test_fixtures_nao_tem_dado_de_cliente(self):
        for path in glob.glob(os.path.join(FIXTURES, "*.json")):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for url in re.findall(r"https?://[^\"\s]+", text):
                self.assertRegex(url, r"^https://(www\.)?(example\.com|instagram\.com/exemplo)/", path)
            self.assertNotIn('"m":', text)  # mensagens do original (trazem nome, site e numeros) ficam fora


class CatalogoTest(unittest.TestCase):
    def test_20_itens_com_ids_do_original(self):
        self.assertEqual([i.legacy_id for i in ITEMS], CATALOGO)
        self.assertEqual(len({i.id for i in ITEMS}), 20)

    def test_perfil_bom_da_100(self):
        r = analyze(profile())
        self.assertEqual(r["overall"], {"score": 100, "good": 20, "fair": 0, "bad": 0, "unavailable": 0,
                                        "notApplicable": 0})

    def test_status_derivado_da_nota(self):
        r = analyze(profile(media__videos=2, location__phone="", location__socialLinks=[]))
        for i in r["items"]:
            self.assertEqual(i["status"], status_for(i["score"]))
        self.assertEqual(by_id(r)["videos"]["status"], "fair")
        self.assertEqual(by_id(r)["phone"]["status"], "bad")

    def test_piores_primeiro_e_sem_nota_no_fim(self):
        r = analyze(profile(location__phone="", location__socialLinks=[], competitors=None))
        scores = [i["score"] for i in r["items"]]
        rated = [s for s in scores if s is not None]
        self.assertEqual(rated, sorted(rated))
        self.assertEqual(scores[-2:], [None, None])
        self.assertEqual(r["items"][0]["id"], "phone")


class GruposSemDadoTest(unittest.TestCase):
    def unavailable(self, result):
        return {i["id"] for i in result["items"] if i["status"] == "unavailable"}

    def test_sem_amostra_de_avaliacoes(self):
        for sample in (None, {"size": 0, "unanswered": 0, "withText": 0, "average": None, "recentSize": 0,
                              "recentAverage": None}):
            r = analyze(profile(reviews__sample=sample))
            self.assertEqual(self.unavailable(r), {"reviews_trend", "reviews_unanswered", "reviews_with_text"})
            self.assertEqual(r["overall"]["good"], 17)

    def test_sem_midia(self):
        r = analyze(profile(media=None))
        self.assertEqual(self.unavailable(r), {"last_owner_photo", "videos", "photos_360"})

    def test_sem_concorrentes_fica_fora_da_nota(self):
        for comp in (None, {"count": 0, "averageReviews": 0, "inTop10ByReviews": True}):
            r = analyze(profile(competitors=comp))
            self.assertEqual(self.unavailable(r), {"top10_reviews", "above_segment_average"})
            self.assertEqual((r["overall"]["good"], r["overall"]["unavailable"]), (18, 2))

    def test_fora_da_nota_nao_pesa(self):
        r = analyze(profile(media=None, reviews__sample=None, location__phone=""))
        self.assertEqual(r["overall"]["score"], (13 * 100) // 14)

    def test_mensagem_de_indisponivel(self):
        msg = by_id(analyze(profile(competitors=None)))["top10_reviews"]["message"]
        self.assertEqual(msg["vars"], {"sections": "competitors"})
        self.assertTrue(msg["template"])


class ContratoTest(unittest.TestCase):
    def test_formato(self):
        r = analyze(profile())
        self.assertEqual(set(r), {"location", "overall", "items", "warnings", "analyzedAt"})
        self.assertEqual(r["location"]["reviewCount"], 40)
        self.assertEqual(r["location"]["rating"], 4.9)
        for i in r["items"]:
            self.assertEqual(set(i), {"id", "originalId", "title", "score", "status", "message"})
            self.assertEqual(set(i["message"]), {"template", "vars"})
            i["message"]["template"].format(**i["message"]["vars"])  # todas as variaveis do texto existem

    def test_mensagens_formatam_em_todos_os_casos_reais(self):
        for path in glob.glob(os.path.join(FIXTURES, "*.json")):
            with open(path, encoding="utf-8") as f:
                for i in analyze(to_profile(json.load(f)))["items"]:
                    i["message"]["template"].format(**i["message"]["vars"])


if __name__ == "__main__":
    unittest.main()


class NaoColetadoTest(unittest.TestCase):
    """`notCollected`: fonte nao coletada = nao avaliado (fora da nota), nunca 0."""

    def test_item_nao_coletado_fica_fora_da_nota(self):
        r = analyze(profile(notCollected=["last_review", "phone"], location__phone=""))
        items = by_id(r)
        self.assertEqual((items["last_review"]["status"], items["phone"]["status"]), ("unavailable", "unavailable"))
        self.assertEqual(items["phone"]["message"]["vars"], {"sections": "phone"})
        self.assertEqual((r["overall"]["good"], r["overall"]["unavailable"], r["overall"]["score"]), (18, 2, 100))

    def test_grupo_nao_coletado(self):
        r = analyze(profile(notCollected=["media"]))
        self.assertEqual({i["id"] for i in r["items"] if i["status"] == "unavailable"},
                         {"last_owner_photo", "videos", "photos_360"})

    def test_sem_lista_nada_muda(self):
        self.assertEqual(analyze(profile(notCollected=[]))["overall"], analyze(profile())["overall"])

    def test_avisos_saem_com_a_analise(self):
        self.assertEqual(analyze(profile(warnings=["Leitor desatualizado: x."]))["warnings"], ["Leitor desatualizado: x."])
        self.assertEqual(analyze(profile())["warnings"], [])
