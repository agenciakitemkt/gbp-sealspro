import json
import os
import tempfile
import unittest
from unittest import mock

import calibration as cal
import storage
from scoring import analyze
from tests.scoring.helpers import referencia
from tests.test_normalize import raw as raw_fixture

LOCATIONS = [
    {"id": "locations/1", "title": "DRA MARIA EXEMPLO - Oftalmologista"},
    {"id": "locations/2", "title": "Clinica Aurora - Saude Integrada"},
    {"id": "locations/3", "title": "Dr. Joao Exemplo - Urologia"},
    {"id": "locations/4", "title": "Dr. Joao Exemplo - Cirurgia"},
    {"id": "locations/5", "title": "Prata Printer - Locação de Impressoras"},
]


def items(**overrides):
    """Itens do original para a Referencia: 100 em tudo, exceto videos (5) = 66 e mídia de clientes (16) = 50."""
    base = {i["legacyId"]: 100 for i in analyze(referencia())["items"]}
    base.update({5: 66, 16: 50})
    base.update({int(k[1:]): v for k, v in overrides.items()})
    return base


def reference_json(scores=None, overall=95, **extra):
    scores = scores or items()
    return {"locationName": "Dra. Maria Exemplo", "score": overall,
            "items": [{"id": i, "title": f"Item {i}", "score": s, "status": 2} for i, s in scores.items()], **extra}


class ParseTest(unittest.TestCase):
    def test_formato_simples(self):
        ref = cal.parse_reference(reference_json(), "a.json")
        self.assertEqual((len(ref.items), ref.overall, ref.items[5]), (21, 95, 66))
        self.assertEqual(ref.warnings, [])

    def test_aninhado_e_tipos_em_texto(self):
        data = {"data": {"result": {"overallScore": "95", "items": [{"id": "0", "nota": "100"}, {"id": "5", "nota": "66,5"}]}}}
        ref = cal.parse_reference(data)
        self.assertEqual((ref.items, ref.overall), ({0: 100, 5: 66.5}, 95))

    def test_nota_geral_em_objeto(self):
        ref = cal.parse_reference({"overall": {"score": 75, "label": "Razoável"}, "checks": [{"id": 1, "score": 50}]})
        self.assertEqual(ref.overall, 75)

    def test_status_do_original_e_ignorado(self):
        ref = cal.parse_reference({"score": 80, "items": [{"id": 1, "score": 100, "status": "bad"}]})
        self.assertEqual(ref.items, {1: 100})

    def test_titulos_dos_itens_nao_viram_nome_do_local(self):
        ref = cal.parse_reference({"locationName": "Clinica X", "items": [{"id": 1, "score": 1, "title": "Website", "name": "Site"}]},
                                  "/tmp/arquivo-qualquer.json")
        self.assertEqual(ref.names, ["Clinica X", "arquivo qualquer"])

    def test_escolhe_a_maior_lista(self):
        data = {"score": 90, "preItems": [{"id": 1, "score": 10}],
                "items": [{"id": 1, "score": 100}, {"id": 2, "score": 50}]}
        self.assertEqual(cal.parse_reference(data).items, {1: 100, 2: 50})

    def test_sem_itens(self):
        ref = cal.parse_reference({"hello": "world"})
        self.assertEqual(ref.items, {})
        self.assertTrue(ref.warnings)

    def test_booleano_nao_e_nota_e_id_repetido_avisa(self):
        ref = cal.parse_reference({"score": 1, "items": [{"id": 1, "score": True}, {"id": 2, "score": 10}, {"id": 2, "score": 20}]})
        self.assertEqual(ref.items, {2: 10})
        self.assertTrue(any("repetido" in w for w in ref.warnings))

    def test_sem_nota_geral_avisa(self):
        ref = cal.parse_reference({"items": [{"id": 1, "score": 10}]})
        self.assertIsNone(ref.overall)
        self.assertTrue(any("nota geral" in w for w in ref.warnings))


class MatchTest(unittest.TestCase):
    def ref(self, *names):
        return cal.Reference(path="x.json", names=list(names))

    def test_por_id(self):
        self.assertEqual(cal.match_location(self.ref("locations/2"), LOCATIONS).location["id"], "locations/2")

    def test_nome_igual_sem_acento_e_caixa(self):
        m = cal.match_location(self.ref("clinica aurora saude integrada"), LOCATIONS)
        self.assertEqual(m.location["id"], "locations/2")

    def test_nome_contido_no_titulo(self):
        self.assertEqual(cal.match_location(self.ref("Dra. Maria Exemplo"), LOCATIONS).location["id"], "locations/1")

    def test_nome_do_arquivo_serve(self):
        ref = cal.parse_reference({"items": [{"id": 1, "score": 1}]}, "/x/maria-exemplo.json")
        self.assertEqual(cal.match_location(ref, LOCATIONS).location["id"], "locations/1")

    def test_ambiguo_nao_chuta(self):
        m = cal.match_location(self.ref("Joao Exemplo"), LOCATIONS)
        self.assertIsNone(m.location)
        self.assertIn("2 locais", m.how)

    def test_parecido(self):
        m = cal.match_location(self.ref("Prata Prnter - Locação de Impressoras"), LOCATIONS)
        self.assertEqual(m.location["id"], "locations/5")
        self.assertIn("parecido", m.how)

    def test_sem_casamento_sugere_proximos(self):
        m = cal.match_location(self.ref("Imobiliaria Exemplo"), LOCATIONS)
        self.assertIsNone(m.location)
        self.assertIn("mais proximos", m.how)


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.result = analyze(referencia())

    def test_referencia_bate_nos_itens_e_diverge_1_ponto_na_geral(self):
        c = cal.compare(cal.parse_reference(reference_json()), self.result, "Referencia", "2026-10-08T00:00:00+00:00")
        self.assertTrue(all(r.diff == 0 for r in c.rows))
        self.assertEqual((c.overall_original, c.overall_engine, c.overall_diff), (95, 95, 0))

    def test_diferenca_por_item_usa_legacy_id(self):
        c = cal.compare(cal.parse_reference(reference_json(items(i16=33))), self.result)
        row = {r.id: r for r in c.rows}[16]
        self.assertEqual((row.original, row.engine, row.diff), (33, 50, 17))
        self.assertEqual(row.title, "Mídias publicadas por clientes")

    def test_item_so_de_um_lado(self):
        scores = items()
        scores.pop(30)
        scores[99] = 40
        rows = {r.id: r for r in cal.compare(cal.parse_reference(reference_json(scores)), self.result).rows}
        self.assertEqual((rows[30].note, rows[30].diff), ("so no motor", None))
        self.assertEqual((rows[99].note, rows[99].diff), ("so no original", None))

    def test_item_indisponivel_nao_conta_como_diferenca(self):
        p = referencia()
        p["collectionErrors"] = {"localPosts": "HTTP 500"}
        c = cal.compare(cal.parse_reference(reference_json()), analyze(p))
        row = {r.id: r for r in c.rows}[29]
        self.assertEqual((row.engine, row.diff, row.note), (None, None, "indisponivel"))

    def test_nota_do_motor_so_com_os_itens_do_original(self):
        scores = {i: 100 for i in range(20)}  # original com 20 itens (como um dos exemplos)
        c = cal.compare(cal.parse_reference(reference_json(scores, overall=100)), self.result)
        self.assertIsNotNone(c.overall_engine_same_items)

    def test_item_que_nao_se_aplica_nos_dois_lados_nao_e_divergencia(self):
        p = referencia()
        p["location"]["servicesEditable"] = False
        scores = items()
        scores.pop(25)  # o original tambem nao avalia Servicos
        c = cal.compare(cal.parse_reference(reference_json(scores)), analyze(p))
        row = {r.id: r for r in c.rows}[25]
        self.assertEqual((row.note, row.diff), ("nao se aplica nos dois", None))
        self.assertEqual(cal.summarize([c]), [])

    def test_original_avalia_e_o_motor_diz_que_nao_se_aplica(self):
        p = referencia()
        p["location"]["servicesEditable"] = False
        row = {r.id: r for r in cal.compare(cal.parse_reference(reference_json()), analyze(p)).rows}[25]
        self.assertEqual((row.original, row.engine, row.note), (100, None, "so no original"))


class FormulaTest(unittest.TestCase):
    def test_formula_nos_contadores_do_original(self):
        self.assertEqual(cal.formula_overall({"good": 19, "fair": 2, "bad": 0}), 95)
        self.assertEqual(cal.formula_overall({"good": 18, "fair": 1, "bad": 2}), 88)
        self.assertEqual(cal.formula_overall({"good": 20, "fair": 0, "bad": 0}), 100)
        self.assertIsNone(cal.formula_overall({"good": 0, "fair": 0, "bad": 0}))


class SummaryTest(unittest.TestCase):
    def comparisons(self):
        result = analyze(referencia())
        a = cal.compare(cal.parse_reference(reference_json(items(i16=20, i5=100)), "a.json"), result)
        b = cal.compare(cal.parse_reference(reference_json(items(i16=40)), "b.json"), result)
        return [a, b]

    def test_ordena_pelo_desvio_medio(self):
        ranked = cal.summarize(self.comparisons(), top=5)
        self.assertEqual([e["id"] for e in ranked], [16, 5])
        self.assertEqual((ranked[0]["wrong"], ranked[0]["max_abs"]), (2, 30))

    def test_respeita_top(self):
        self.assertEqual(len(cal.summarize(self.comparisons(), top=1)), 1)

    def test_sem_divergencia(self):
        c = cal.compare(cal.parse_reference(reference_json()), analyze(referencia()))
        self.assertEqual(cal.summarize([c]), [])

    def test_texto_do_resumo(self):
        comps = self.comparisons()
        text = cal.render_summary(comps, [("c.json", "sem casamento")], 5, ["Local sem referencia"])
        self.assertIn("Itens com maior divergencia", text)
        self.assertIn("a.json [desconhecida]: original 20 -> motor 50 (+30)", text)
        self.assertIn("Locais ativos sem referencia no arquivo (nada a comparar): Local sem referencia", text)
        self.assertIn("c.json: sem casamento", text)
        self.assertIn("O config nao foi alterado.", text)

    def test_tabela(self):
        c = cal.compare(cal.parse_reference(reference_json(items(i16=33)), "ref.json"), analyze(referencia()), "Referencia", "2026-10-08T00:00:00+00:00")
        text = cal.render_comparison(c)
        self.assertIn("original", text)
        self.assertRegex(text, r"16\s+Mídias publicadas por clientes\s+33\s+50\s+\+17\s+\*")
        self.assertIn("Nota geral: original 95 | motor 95 | dif 0", text)
        self.assertRegex(text, r"\n  0  Número de telefone\s+100\s+100\s+0\n")  # zero sem sinal


class CalibrateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.refs = os.path.join(tmp.name, "reference")
        os.makedirs(self.refs)
        for p in (mock.patch.object(storage, "DATA", tmp.name), mock.patch.object(storage, "DB", os.path.join(tmp.name, "t.db"))):
            p.start()
            self.addCleanup(p.stop)
        self.db = storage.connect()
        self.addCleanup(self.db.close)
        storage.upsert_location(self.db, "locations/1", "accounts/1", "Clinica X", "BH", "Conta")
        storage.upsert_location(self.db, "locations/2", "accounts/1", "Outro Local", "BH", "Conta")
        self.db.commit()
        storage.save_raw(self.db, "locations/1", raw_fixture())
        self.out = []

    def write(self, name, data):
        with open(os.path.join(self.refs, name), "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))

    def run_cal(self, manual=None):
        return cal.calibrate(self.db, self.refs, manual, 5, self.out.append)

    def engine_scores(self):
        result = analyze(__import__("collector.normalize", fromlist=["normalize"]).normalize(raw_fixture()))
        return {i["legacyId"]: i["score"] for i in result["items"]}, result["overall"]["score"]

    def test_pasta_vazia_explica_o_que_colocar(self):
        self.run_cal()
        self.assertIn("Nenhum arquivo .json", self.out[0])

    def test_fluxo_completo_com_casamento_por_nome(self):
        scores, overall = self.engine_scores()
        scores[5] = scores[5] - 10 if scores[5] >= 10 else 0
        self.write("clinica-x.json", {"locationName": "Clinica X", "score": overall, "items": [{"id": i, "score": s} for i, s in scores.items()]})
        comps = self.run_cal()
        self.assertEqual(len(comps), 1)
        text = "\n".join(self.out)
        self.assertIn("casado com Clinica X", text)
        self.assertIn("Itens com maior divergencia", text)
        self.assertEqual([r.id for r in comps[0].rows if r.diff], [5])

    def test_ajuste_manual(self):
        scores, overall = self.engine_scores()
        self.write("exemplo.json", {"locationName": "Imobiliaria Exemplo", "score": overall, "items": [{"id": i, "score": s} for i, s in scores.items()]})
        self.assertEqual(self.run_cal(), [])  # sem casamento por nome
        self.assertIn('--map "exemplo.json"=', "\n".join(self.out))
        self.out.clear()
        comps = self.run_cal({"exemplo.json": storage.find_location(self.db, "Clinica X")})
        self.assertEqual(len(comps), 1)
        self.assertIn("ajuste manual", "\n".join(self.out))

    def test_local_sem_coleta(self):
        self.write("outro.json", {"locationName": "Outro Local", "score": 50, "items": [{"id": 1, "score": 50}]})
        self.assertEqual(self.run_cal(), [])
        self.assertIn("nao tem coleta guardada", "\n".join(self.out))

    def test_json_invalido_e_sem_itens_sao_ignorados_sem_parar(self):
        self.write("quebrado.json", "{ nao e json")
        self.write("vazio.json", {"a": 1})
        self.run_cal()
        text = "\n".join(self.out)
        self.assertIn("quebrado.json: nao foi possivel ler", text)
        self.assertIn("vazio.json: nenhuma lista de itens", text)

    def test_nao_altera_o_config(self):
        from scoring import config
        before = json.dumps(config.CONFIG, sort_keys=True, default=str)
        scores, overall = self.engine_scores()
        self.write("x.json", {"locationName": "Clinica X", "score": overall, "items": [{"id": i, "score": 0} for i in scores]})
        self.run_cal()
        self.assertEqual(json.dumps(config.CONFIG, sort_keys=True, default=str), before)


def multi_json(**local_overrides):
    """Arquivo no formato do GBP Check original (varios locais), com nomes ficticios."""
    ids = {"0": "Numero de telefone", "1": "Website", "25": "Servicos"}
    local = {"name": "Clinica X", "businessId": "1", "analisadoHa": "8 dias atrás", "overall": 90,
             "counts": {"bad": 1, "fair": 0, "good": 9}, "rating": "4.5", "reviews": 2,
             "starsDe1a5": [0, 0, 0, 1, 1],  # 1 -> 5 estrelas
             "scores": {"0": 100, "1": 100, "25": 100}}
    local.update(local_overrides)
    other = {"name": "Outro", "businessId": "999", "analisadoHa": "28 dias atrás", "overall": 50,
             "scores": {"0": 50}}
    return {"fonte": "GBP Check teste", "avisos": ["Aviso um.", "Aviso dois."], "ids_dos_itens": ids,
            "locais": [local, other]}


class MultiLocalParseTest(unittest.TestCase):
    def parse(self, **kw):
        return cal.parse_reference_file(multi_json(**kw), "/x/gbpcheck_original.json")

    def test_le_um_local_por_entrada(self):
        refs, meta = self.parse()
        self.assertEqual([r.label for r in refs], ["Clinica X", "Outro"])
        r = refs[0]
        self.assertEqual((r.items, r.overall, r.business_id), ({0: 100, 1: 100, 25: 100}, 90, "1"))
        self.assertEqual(r.counts, {"bad": 1, "fair": 0, "good": 9})
        self.assertEqual((r.rating, r.reviews), (4.5, 2))

    def test_estrelas_vem_de_1_a_5_e_ficam_de_5_a_1(self):
        refs, _ = self.parse()
        self.assertEqual(refs[0].stars, [1, 1, 0, 0, 0])

    def test_avisos_fonte_e_nomes_dos_itens(self):
        _, meta = self.parse()
        self.assertEqual(meta["avisos"], ["Aviso um.", "Aviso dois."])
        self.assertEqual(meta["fonte"], "GBP Check teste")
        self.assertEqual(meta["item_names"][25], "Servicos")

    def test_item_ausente_em_scores_nao_se_aplica(self):
        refs, _ = self.parse(scores={"0": 100})
        self.assertNotIn(25, refs[0].items)

    def test_idade_e_cautela(self):
        recent, old = self.parse()[0]
        self.assertEqual((recent.age_days, recent.recency), (8, "recente"))
        self.assertEqual((old.age_days, old.recency), (28, "antiga"))

    def test_leitura_de_idades(self):
        for text, days in (("14 horas atrás", 14 / 24), ("8 dias atrás", 8), ("1 mês atrás", 30),
                           ("2 semanas atrás", 14), ("há um dia", 1), ("agora", 0), ("30 minutos atrás", 30 / 1440)):
            self.assertAlmostEqual(cal.parse_age_days(text), days, msg=text)
        self.assertIsNone(cal.parse_age_days("Nunca"))
        self.assertIsNone(cal.parse_age_days(None))

    def test_14_horas_e_8_dias_sao_recentes_e_28_dias_nao(self):
        for text, expected in (("14 horas atrás", "recente"), ("8 dias atrás", "recente"), ("28 dias atrás", "antiga"),
                               ("1 mês atrás", "antiga"), ("Nunca", "desconhecida")):
            ref = cal.parse_reference_file(multi_json(analisadoHa=text))[0][0]
            self.assertEqual(ref.recency, expected, text)

    def test_formato_antigo_continua_funcionando(self):
        refs, meta = cal.parse_reference_file(reference_json(), "antigo.json")
        self.assertEqual((len(refs), len(refs[0].items), meta["avisos"]), (1, 21, []))
        self.assertEqual(refs[0].recency, "desconhecida")

    def test_nota_invalida_avisa(self):
        refs, _ = self.parse(scores={"0": 100, "x": 5, "1": "abc"})
        self.assertEqual(refs[0].items, {0: 100})
        self.assertEqual(sum("ignorado" in w for w in refs[0].warnings), 2)


class BusinessIdMatchTest(unittest.TestCase):
    LOCS = [{"id": "locations/111", "title": "Clinica Aurora - Saude Integrada"},
            {"id": "locations/222", "title": "Clinica Aurora - Odontologia"},
            {"id": "locations/333", "title": "Instituto Maria Exemplo - Harmonizacao Orofacial"}]

    def ref(self, name, business_id=None):
        return cal.Reference(path="x.json", name=name, names=[name], business_id=business_id)

    def test_nome_encurtado_casa_e_businessid_confere(self):
        m = cal.match_location(self.ref("Instituto Maria Exemplo", "333"), self.LOCS)
        self.assertEqual(m.location["id"], "locations/333")
        self.assertIn("businessId confere", m.how)

    def test_nome_ambiguo_e_resolvido_pelo_businessid(self):
        m = cal.match_location(self.ref("Clinica Aurora", "222"), self.LOCS)
        self.assertEqual(m.location["id"], "locations/222")
        self.assertIn("businessId coincide", m.how)

    def test_nome_ambiguo_sem_businessid_pede_map(self):
        m = cal.match_location(self.ref("Clinica Aurora", "7"), self.LOCS)
        self.assertIsNone(m.location)
        self.assertIn("2 locais", m.how)

    def test_conflito_entre_nome_e_businessid_nao_casa(self):
        m = cal.match_location(self.ref("Instituto Maria Exemplo", "111"), self.LOCS)
        self.assertIsNone(m.location)
        self.assertIn("conflito", m.how)

    def test_businessid_desconhecido_nao_atrapalha_o_nome(self):
        m = cal.match_location(self.ref("Instituto Maria Exemplo", "5"), self.LOCS)
        self.assertEqual(m.location["id"], "locations/333")


class MultiLocalCompareTest(unittest.TestCase):
    def test_extras_de_perfil_contadores_e_formula(self):
        ref = cal.parse_reference_file(multi_json(), "g.json")[0][0]
        c = cal.compare(ref, analyze(referencia()), "Referencia", "2026-10-08T00:00:00+00:00")
        checks = {label: (o, e) for label, o, e in c.profile_checks}
        self.assertEqual(checks["avaliacoes"], (2, 22))
        self.assertEqual(checks["estrelas 5 a 1"], ([1, 1, 0, 0, 0], [22, 0, 0, 0, 0]))
        self.assertEqual(c.formula_original, 90)
        text = cal.render_comparison(c)
        self.assertIn("RECENTE", text)
        self.assertIn("contadores (fraco/razoavel/bom): original 1/0/9 | motor 0/2/19", text)
        self.assertIn("avaliacoes: original 2 | coleta 22 -> DIFERE", text)
        self.assertIn("-> confere", text)

    def test_analise_antiga_vem_sinalizada(self):
        ref = cal.parse_reference_file(multi_json(), "g.json")[0][1]
        text = cal.render_comparison(cal.compare(ref, analyze(referencia()), "S", "2026-10-08T00:00:00+00:00"))
        self.assertIn("ANTIGA", text)
        self.assertIn("cautela", text)

    def test_resumo_separa_recentes_das_antigas(self):
        refs = cal.parse_reference_file(multi_json(scores={"0": 100, "5": 100}), "g.json")[0]
        result = analyze(referencia())
        comps = [cal.compare(r, result, "S", "2026-10-08T00:00:00+00:00") for r in refs]
        text = cal.render_summary(comps, [], 5)
        self.assertIn("RESUMO: 2 local(is) comparado(s) (1 com analise recente)", text)
        self.assertIn("nas analises RECENTES", text)
        self.assertIn("[antiga]", text)


class MultiLocalCalibrateTest(CalibrateTest):
    """Mesmo cenario do CalibrateTest, mas com o arquivo no formato do GBP Check."""

    def multi(self, scores, **kw):
        local = {"name": "Consultorio sem relacao", "businessId": "1", "analisadoHa": "14 horas atrás",
                 "overall": 100, "scores": {str(i): s for i, s in scores.items() if s is not None}, **kw}
        far = {"name": "Local de outra conta", "businessId": "777", "analisadoHa": "28 dias atrás", "overall": 50,
               "scores": {"0": 50}}
        return {"avisos": ["Aviso de teste."], "ids_dos_itens": {"0": "Telefone"}, "locais": [local, far]}

    def test_arquivo_com_varios_locais(self):
        scores, overall = self.engine_scores()
        self.write("gbpcheck_original.json", self.multi(scores))
        storage.set_active(self.db, "locations/2", True)
        self.db.commit()
        comps = self.run_cal()
        text = "\n".join(self.out)
        self.assertEqual(len(comps), 1)
        self.assertIn("aviso do arquivo: Aviso de teste.", text)
        self.assertIn("businessId coincide", text)  # o nome nao casa com nenhum local, o businessId sim
        self.assertIn("RECENTE", text)
        self.assertIn("Local de outra conta: sem casamento", text)
        self.assertIn("Locais ativos sem referencia no arquivo (nada a comparar): Outro Local", text)

    def test_map_pelo_nome_do_local_dentro_do_arquivo(self):
        scores, _ = self.engine_scores()
        data = self.multi(scores, businessId="55")
        self.write("gbpcheck_original.json", data)
        self.assertEqual(len(self.run_cal()), 0)
        self.out.clear()
        manual = {"Local de outra conta": storage.find_location(self.db, "Clinica X"),
                  "Consultorio sem relacao": storage.find_location(self.db, "Clinica X")}
        comps = self.run_cal(manual)
        self.assertEqual(len(comps), 2)
        self.assertIn("ajuste manual", "\n".join(self.out))


class SelecaoDeArquivosTest(unittest.TestCase):
    def test_versao_mais_recente_da_mesma_familia_e_a_principal(self):
        used, history = cal.select_reference_files(["gbpcheck_original.json", "gbpcheck_original_2026-10-08.json"])
        self.assertEqual((used, history), (["gbpcheck_original_2026-10-08.json"], ["gbpcheck_original.json"]))

    def test_varias_datas(self):
        names = ["g_2026-10-01.json", "g_2026-10-08.json", "g_2026-09-30.json"]
        self.assertEqual(cal.select_reference_files(names), (["g_2026-10-08.json"], ["g_2026-09-30.json", "g_2026-10-01.json"]))

    def test_arquivos_de_familias_diferentes_nao_se_misturam(self):
        used, history = cal.select_reference_files(["a.json", "b_2026-10-08.json", "exemplo.json"])
        self.assertEqual((used, history), (["a.json", "b_2026-10-08.json", "exemplo.json"], []))


class RawValuesTest(unittest.TestCase):
    def test_valores_dos_itens_19_29_e_30(self):
        from tests.scoring.helpers import NOW, days_ago, media, review
        p = referencia()
        p["posts"] = [{"type": "STANDARD", "createdAt": days_ago(43)}, {"type": "STANDARD", "createdAt": days_ago(60)}]
        p["media"] = [media(created=days_ago(152)), media(created="1970-01-01T00:00:00Z")]
        p["reviews"] = [review(replied=False, created=days_ago(3)), review(replied=False, created=days_ago(0)), review()]
        raw = cal.raw_values(p, NOW)
        self.assertEqual((raw["post_days"], raw["posts"]), (43, 2))
        self.assertEqual((raw["media_days"], raw["media_dated"]), (152, 1))  # a data de 1970 nao conta
        self.assertEqual((raw["unanswered"], raw["reviews"], raw["unanswered_ages"]), (2, 3, [0, 3]))

    def test_sem_postagens_nem_midias(self):
        from tests.scoring.helpers import NOW
        p = referencia()
        p["posts"], p["media"], p["reviews"] = [], [], []
        raw = cal.raw_values(p, NOW)
        self.assertEqual((raw["post_days"], raw["media_days"], raw["unanswered"]), (None, None, 0))


class RelatorioDeDivergenciasTest(MultiLocalCalibrateTest):
    """Reaproveita o cenario de arquivo com varios locais (banco temporario com uma coleta)."""

    def divergent(self):
        scores, overall = self.engine_scores()
        scores[19] = 0   # o original zerou o item 19; o motor da outra nota
        return self.multi({k: v for k, v in scores.items() if v is not None}, overall=overall)

    def test_principal_e_historico(self):
        scores, _ = self.engine_scores()
        self.write("gbp_original.json", self.multi(scores))
        self.write("gbp_original_2026-10-08.json", self.divergent())
        self.run_cal()
        text = "\n".join(self.out)
        self.assertIn("Referencia principal: gbp_original_2026-10-08.json", text)
        self.assertIn("Historico (nao usado", text)
        self.assertNotIn("##### gbp_original.json", text)

    def test_incluir_historico_compara_os_dois(self):
        scores, _ = self.engine_scores()
        self.write("gbp_original.json", self.multi(scores))
        self.write("gbp_original_2026-10-08.json", self.divergent())
        comps = cal.calibrate(self.db, self.refs, None, 5, self.out.append, include_history=True)
        self.assertEqual(len(comps), 2)

    def test_so_divergencias_mostra_valores_brutos_e_omite_a_tabela(self):
        self.write("gbp_original_2026-10-08.json", self.divergent())
        cal.calibrate(self.db, self.refs, None, 5, self.out.append, only_divergences=True)
        text = "\n".join(self.out)
        self.assertIn("DIVERGENCIAS POR LOCAL", text)
        self.assertRegex(text, r"\[19\] Avaliações sem resposta: original 0 -> motor \d+")
        self.assertIn("valores usados:", text)
        self.assertIn("sem resposta de", text)
        self.assertIn("VALORES BRUTOS DOS ITENS 19, 29 E 30", text)
        self.assertNotIn("id  item", text)  # sem a tabela completa por local

    def test_tabela_completa_continua_sendo_o_padrao(self):
        self.write("gbp_original_2026-10-08.json", self.divergent())
        self.run_cal()
        text = "\n".join(self.out)
        self.assertIn(" id  item", text)
        self.assertIn("DIVERGENCIAS POR LOCAL", text)


if __name__ == "__main__":
    unittest.main()
