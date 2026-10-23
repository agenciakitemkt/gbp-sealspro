"""calibrar-pre: compara o motor da Pre com as notas do original, separando decisao nossa de divergencia de regra."""

import copy
import json
import os
import tempfile
import unittest

from calibration_pre import calibrate_pre, compare_case
from tests.scoring.pre.test_engine import fixture


def no_competitors(case):
    """O original, sem concorrentes, da 100 nos dois itens de ranking."""
    c = copy.deepcopy(case)
    c["ncomp"] = 0
    c["pd"]["avg_reviews_count_all"] = 0
    for i in c["items"]:
        if i["id"] in ("reviews_ranking_top_10", "reviews_ranking_average") and i["s"] != 100:
            c["stats"]["bad_items"] -= 1
            c["stats"]["good_items"] += 1
            i["s"] = 100
    g, f, n = c["stats"]["good_items"], c["stats"]["fair_items"], len(c["items"])
    c["stats"]["overall_score"] = (g * 100 + f * 50) // n
    return c


class CompararTest(unittest.TestCase):
    def test_caso_igual(self):
        r = compare_case(fixture("caso_20_itens.json"))
        self.assertTrue(r.totals_match)
        self.assertEqual(r.rule_divergences, [])
        self.assertEqual(r.decision_rows, [])

    def test_divergencia_de_regra(self):
        case = fixture("caso_20_itens.json")
        item = next(i for i in case["items"] if i["id"] == "phone")
        item["s"] = 0
        r = compare_case(case)
        self.assertEqual([d.original_id for d in r.rule_divergences], ["phone"])
        self.assertEqual((r.rule_divergences[0].original, r.rule_divergences[0].engine), (0, 100))

    def test_sem_concorrentes_e_decisao_nossa(self):
        r = compare_case(no_competitors(fixture("caso_20_itens.json")))
        self.assertEqual(r.rule_divergences, [])
        self.assertEqual({d.original_id for d in r.decision_rows}, {"reviews_ranking_top_10", "reviews_ranking_average"})
        self.assertFalse(r.totals_match)
        self.assertTrue(r.totals_match_as_original)

    def test_item_que_o_original_deixou_fora(self):
        r = compare_case(fixture("caso_17_itens.json"))
        rows = {x.original_id: x for x in r.rows}
        self.assertIsNone(rows["videos"].original)
        self.assertIsNone(rows["videos"].engine)
        self.assertTrue(rows["videos"].same)


class RelatorioTest(unittest.TestCase):
    def run_on(self, cases, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pre.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cases, f)
            lines = []
            results = calibrate_pre(path, out=lines.append, **kw)
            return results, "\n".join(lines)

    def test_resumo(self):
        cases = [fixture(n) for n in ("caso_20_itens.json", "caso_17_itens.json", "caso_14_itens.json")]
        cases.append(no_competitors(cases[0]))
        results, text = self.run_on(cases)
        self.assertEqual(len(results), 4)
        self.assertIn("Nota geral e contadores iguais ao original: 3 de 4", text)
        self.assertIn("Contando como o original os itens que tiramos por decisao: 4 de 4", text)
        self.assertIn("divergencias de regra: 0", text)
        self.assertIn("[decisao]", text)
        self.assertIn("Negócio Exemplo B", text)  # tabela completa sem --so-divergencias

    def test_so_divergencias(self):
        _, text = self.run_on([fixture("caso_17_itens.json")], only_divergences=True)
        self.assertIn("nenhum caso diverge", text)
        self.assertNotIn("Negócio Exemplo B", text)

    def test_arquivo_ausente(self):
        lines = []
        self.assertEqual(calibrate_pre("/nao/existe.json", out=lines.append), [])
        self.assertIn("nao encontrado", lines[0])


if __name__ == "__main__":
    unittest.main()
