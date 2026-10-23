import copy
import subprocess
import sys
import unittest

from scoring import analyze, config
from scoring.base import status_for
from scoring.items import ITEMS
from tests.scoring.helpers import NOW, referencia

CATALOGO = [0, 1, 2, 3, 4, 5, 6, 7, 14, 15, 16, 17, 18, 19, 20, 25, 26, 27, 28, 29, 30]


def by_id(result):
    return {i["id"]: i for i in result["items"]}


class AceiteReferenciaTest(unittest.TestCase):
    """Critério de aceite da seção 10 do CLAUDE.md."""

    def setUp(self):
        self.result = analyze(referencia())

    def test_21_itens_do_catalogo(self):
        self.assertEqual(sorted(i["legacyId"] for i in self.result["items"]), CATALOGO)

    def test_contadores_0_fraco_2_razoavel_19_bom(self):
        o = self.result["overall"]
        self.assertEqual((o["bad"], o["fair"], o["good"], o["unavailable"]), (0, 2, 19, 0))

    def test_itens_com_problema(self):
        items = by_id(self.result)
        fair = {k for k, v in items.items() if v["status"] == "fair"}
        self.assertEqual(fair, {"customer_media", "videos"})
        self.assertEqual(items["customer_media"]["message"]["vars"], {"current": 1, "recommended": 3})
        self.assertEqual(items["videos"]["message"]["vars"], {"current": 2, "recommended": 3})

    def test_nota_geral_e_95_como_no_original(self):
        self.assertEqual(self.result["overall"]["score"], 95)  # (19*100 + 2*50) // 21

    def test_piores_primeiro(self):
        scores = [i["score"] for i in self.result["items"]]
        self.assertEqual(scores, sorted(scores))
        self.assertEqual([i["id"] for i in self.result["items"][:2]], ["customer_media", "videos"])


class StatusTest(unittest.TestCase):
    def test_limites(self):
        self.assertEqual([status_for(s) for s in (0, 49, 50, 66, 99, 100)],
                         ["bad", "bad", "fair", "fair", "fair", "good"])
        self.assertEqual(status_for(None), "unavailable")

    def test_status_sempre_derivado_da_nota(self):
        for i in analyze(referencia())["items"]:
            self.assertEqual(i["status"], status_for(i["score"]))


class IndisponivelTest(unittest.TestCase):
    def broken(self, **errors):
        p = referencia()
        p["collectionErrors"] = errors
        return analyze(p)

    def unavailable(self, result):
        return {i["id"] for i in result["items"] if i["status"] == "unavailable"}

    def test_falha_em_media(self):
        r = self.broken(media="HTTP 500")
        self.assertEqual(self.unavailable(r), {"videos", "logo", "cover", "owner_media", "total_media",
                                               "last_owner_media"})
        for i in r["items"]:
            if i["status"] == "unavailable":
                self.assertIsNone(i["score"])  # nunca nota 0

    def test_falha_em_midia_de_clientes(self):
        self.assertEqual(self.unavailable(self.broken(mediaCustomers="x")), {"customer_media", "total_media"})

    def test_falha_em_avaliacoes(self):
        self.assertEqual(self.unavailable(self.broken(reviews="x")),
                         {"reviews_count", "reviews_average", "reviews_unanswered", "reviews_no_comment",
                          "reviews_trend"})

    def test_falha_em_postagens(self):
        self.assertEqual(self.unavailable(self.broken(localPosts="x")), {"last_post"})

    def test_lista_de_avaliacoes_incompleta_tambem_e_indisponivel(self):
        p = referencia()
        p["reviewsComplete"] = False
        self.assertIn("reviews_count", self.unavailable(analyze(p)))

    def test_fora_da_media_e_dos_contadores(self):
        r = self.broken(localPosts="x")
        o = r["overall"]
        self.assertEqual((o["good"], o["fair"], o["bad"], o["unavailable"]), (18, 2, 0, 1))
        scores = [i["score"] for i in r["items"] if i["score"] is not None]
        self.assertEqual(len(scores), 20)
        self.assertEqual(o["score"], (18 * 100 + 2 * 50) // 20)  # indisponivel fora do total

    def test_todas_as_secoes_falhando_deixa_so_os_itens_sem_dependencia(self):
        r = self.broken(reviews="x", media="x", mediaCustomers="x", localPosts="x")
        sem_dependencia = [i for i in ITEMS if not i.requires]
        self.assertEqual(r["overall"]["unavailable"], len(ITEMS) - len(sem_dependencia))
        self.assertEqual(r["overall"]["good"], len(sem_dependencia))
        self.assertEqual(r["overall"]["score"], 100)

    def test_sem_nenhum_item_avaliado_nao_inventa_nota(self):
        from scoring.base import overall_score as _overall_score
        self.assertIsNone(_overall_score([]))

    def test_mensagem_de_indisponivel_usa_template(self):
        msg = by_id(self.broken(localPosts="x"))["last_post"]["message"]
        self.assertEqual(msg["template"], "Não foi possível coletar este dado.")
        self.assertEqual(msg["vars"], {"sections": "localPosts"})  # fica para depuracao, fora do texto
        self.assertNotIn("localPosts", msg["template"].format(**msg["vars"]))


class ContratoTest(unittest.TestCase):
    def test_formato(self):
        r = analyze(referencia())
        self.assertEqual(set(r), {"location", "overall", "items", "analyzedAt"})
        self.assertEqual(set(r["overall"]), {"score", "good", "fair", "bad", "unavailable", "notApplicable"})
        for i in r["items"]:
            self.assertEqual(set(i), {"id", "legacyId", "title", "score", "status", "message"})
            self.assertEqual(set(i["message"]), {"template", "vars"})

    def test_toda_mensagem_formata_com_suas_variaveis(self):
        vazio = referencia()
        vazio["location"].update(phone="", website="", hours={}, specialHours=[], description="", services=[],
                                 openingDate=None, name="", rating=0.0)
        vazio.update(reviews=[], media=[], customerMedia=[], posts=[])
        for profile in (referencia(), vazio):
            for item in analyze(profile)["items"]:
                m = item["message"]
                self.assertTrue(m["template"].format(**m["vars"]), item["id"])

    def test_cada_item_do_catalogo_tem_calibracao_declarada(self):
        for item in ITEMS:
            self.assertIn(config.CONFIG[item.id]["estado"], (config.MEDIDO, config.PARCIAL, config.HIPOTESE),
                          item.id)
        self.assertEqual(set(config.CONFIG), {i.id for i in ITEMS})


class NotaGeralTest(unittest.TestCase):
    """Nota geral = piso de (bons*100 + razoaveis*50) / itens avaliados. Confirmada no original."""

    def test_formula_nos_casos_do_original(self):
        from scoring.base import overall_score as _overall_score
        cases = [  # (bons, razoaveis, fracos) -> nota geral do original
            ((19, 2, 0), 95),   # caso de referencia
            ((18, 1, 2), 88),
            ((19, 1, 1), 92),
            ((20, 1, 0), 97),
            ((20, 0, 1), 95),   # tres locais
            ((21, 0, 0), 100),
            ((20, 0, 0), 100),  # local com 20 itens
        ]
        for (g, f, b), expected in cases:
            self.assertEqual(_overall_score(["good"] * g + ["fair"] * f + ["bad"] * b), expected, (g, f, b))

    def test_usa_o_piso_e_nao_arredonda(self):
        from scoring.base import overall_score as _overall_score
        self.assertEqual(_overall_score(["good"] * 2 + ["bad"]), 66)  # 66,67

    def test_fracos_pesam_zero(self):
        from scoring.base import overall_score as _overall_score
        self.assertEqual(_overall_score(["bad", "bad"]), 0)

    def test_fora_do_total_indisponivel_e_nao_se_aplica(self):
        from scoring.base import overall_score as _overall_score
        self.assertEqual(_overall_score(["good", "unavailable", "not_applicable"]), 100)
        self.assertIsNone(_overall_score(["unavailable", "not_applicable"]))
        self.assertIsNone(_overall_score([]))


class NaoSeAplicaTest(unittest.TestCase):
    def sem_servicos_editaveis(self):
        p = referencia()
        p["location"]["servicesEditable"] = False
        p["location"]["services"] = []
        return analyze(p)

    def test_servicos_nao_se_aplica_quando_a_categoria_nao_aceita(self):
        r = self.sem_servicos_editaveis()
        item = by_id(r)["services"]
        self.assertEqual((item["score"], item["status"]), (None, "not_applicable"))
        self.assertIn("categoria", item["message"]["template"])

    def test_fica_fora_da_media_e_dos_contadores_e_ao_final(self):
        r = self.sem_servicos_editaveis()
        o = r["overall"]
        self.assertEqual((o["good"], o["fair"], o["bad"], o["unavailable"], o["notApplicable"]), (18, 2, 0, 0, 1))
        self.assertEqual(o["score"], (18 * 100 + 2 * 50) // 20)
        self.assertEqual(r["items"][-1]["id"], "services")

    def test_nao_e_zero(self):  # nunca vira nota 0
        self.assertIsNone(by_id(self.sem_servicos_editaveis())["services"]["score"])

    def test_sem_servicos_mas_editavel_e_nota_zero(self):  # caso real: pode editar, nao tem
        p = referencia()
        p["location"]["services"] = []
        item = by_id(analyze(p))["services"]
        self.assertEqual((item["score"], item["status"]), (0, "bad"))

    def test_sem_metadata_na_leitura_o_item_continua_valendo(self):
        p = referencia()
        p["location"]["servicesEditable"] = None
        self.assertEqual(by_id(analyze(p))["services"]["status"], "good")


class CurvasHipoteticasRegistradasTest(unittest.TestCase):
    """Itens 19, 29 e 30: curvas hipótese, com os pontos medidos em `observed` e reproduzidos pelo motor."""

    def test_estado_e_hipotese(self):
        for item in ("reviews_unanswered", "last_post", "last_owner_media"):
            self.assertEqual(config.CONFIG[item]["estado"], config.HIPOTESE, item)

    def test_pontos_observados_estao_no_config_e_o_motor_os_reproduz(self):
        from scoring.curves import step_score
        for item in ("last_post", "last_owner_media"):
            c = config.CONFIG[item]
            self.assertTrue(c["observed"], item)
            for point in c["observed"]:
                self.assertEqual(step_score(point["days"], c["steps"], c["beyond"]), point["score"], (item, point))

    def test_item_30_registra_que_o_zero_comeca_entre_87_e_151_dias(self):
        c = config.CONFIG["last_owner_media"]
        self.assertEqual(c["zero_starts_between_days"], (87, 151))
        self.assertIn("desconhecido", c["obs"])

    def test_item_19_registra_pontos_medidos_e_a_regra_por_percentual_em_aberto(self):
        c = config.CONFIG["reviews_unanswered"]
        self.assertEqual(sorted(p["unanswered"] for p in c["observed"]), [0, 1, 4, 8])
        self.assertIn("0, 1, 4 e 8", c["obs"])
        self.assertIn("percentual NAO foi descartada", c["obs"])


class PurezaTest(unittest.TestCase):
    def test_deterministico_e_nao_altera_a_entrada(self):
        p = referencia()
        antes = copy.deepcopy(p)
        self.assertEqual(analyze(p), analyze(p))
        self.assertEqual(p, antes)

    def test_now_padrao_e_a_data_da_coleta(self):
        self.assertEqual(analyze(referencia())["analyzedAt"], NOW.isoformat())

    def test_nao_importa_rede_nem_api(self):
        code = ("import sys, scoring.engine; "
                "bad = {'requests', 'gbp_auth', 'storage', 'collector', 'sqlite3'} & set(sys.modules); "
                "sys.exit(1 if bad else 0)")
        self.assertEqual(subprocess.run([sys.executable, "-c", code]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
