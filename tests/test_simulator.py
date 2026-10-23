import random
import unittest
from datetime import date

import simulator as sim


def shown_float(total_stars, total):
    """Conta direta, para conferir: media com uma casa, arredondando para cima a partir de 0,05."""
    return int(total_stars * 10 / total + 0.5 + 1e-9)


def brute_needed(s, t, target):
    n = 0
    while shown_float(s + 5 * n, t + n) < target:
        n += 1
    return n


def brute_drop(s, t, stars, ceiling):
    for n in range(0, 5000):
        if shown_float(s + stars * n, t + n) <= ceiling:
            return n
    return None


class ContasTest(unittest.TestCase):
    def test_nota_mostrada_arredonda_como_o_google(self):
        self.assertEqual(sim.shown(17, 4), 43)   # 4,25 aparece como 4,3
        self.assertEqual(sim.shown(11, 3), 37)   # 3,67
        self.assertEqual(sim.shown(5, 1), 50)
        self.assertIsNone(sim.shown(0, 0))

    def test_caso_feito_a_mao(self):
        s, t = 11, 3  # 5, 5 e 1 estrela: 3,7
        self.assertEqual(sim.needed_for(s, t, 39), 1)   # 4,0
        self.assertEqual(sim.needed_for(s, t, 43), 3)   # 4,33
        self.assertEqual(sim.needed_for(s, t, 47), 9)   # 4,67 (com 8: 4,64 = 4,6)
        self.assertEqual(sim.to_drop(s, t, 1, 29), 2)   # 2,6
        self.assertEqual(sim.to_drop(s, t, 2, 29), 3)   # 2,83
        self.assertIsNone(sim.to_drop(s, t, 3, 29))     # com 3 estrelas a media nunca fica abaixo de 3,0

    def test_confere_com_forca_bruta(self):
        rng = random.Random(7)
        for _ in range(400):
            dist = [rng.randint(0, 40) for _ in range(5)]
            s, t = sim.totals(dist)
            if not t:
                continue
            cur = sim.shown(s, t)
            self.assertEqual(cur, shown_float(s, t), dist)
            for target in range(cur, 51):
                self.assertEqual(sim.needed_for(s, t, target), brute_needed(s, t, target), (dist, target))
            for ceiling in (29, 38, 42, 46):
                if ceiling < cur:
                    for stars in (1, 2, 3):
                        expected = brute_drop(s, t, stars, ceiling)
                        self.assertEqual(sim.to_drop(s, t, stars, ceiling), expected, (dist, stars, ceiling))

    def test_distribuicao_vai_de_5_a_1_estrela(self):
        self.assertEqual(sim.totals([1, 0, 0, 0, 1]), (6, 2))
        self.assertEqual(sim.totals(None, rating=4.5, count=10), (45, 10))
        self.assertEqual(sim.totals([0, 0, 0, 0, 0]), (0, 0))


class SimularTest(unittest.TestCase):
    def test_meta_padrao_e_a_proxima_faixa(self):
        r = sim.simulate([2, 0, 0, 0, 1], today=date(2026, 10, 10))
        self.assertEqual(r["current"], "3,7")
        self.assertEqual(r["zone"]["name"], "Baixa")
        self.assertEqual(r["target_label"], "3,9")
        self.assertEqual(r["needed"], 1)
        self.assertEqual([g["needed"] for g in r["growth"]], [1, 3, 9])
        self.assertEqual([(x["stars"], x["count"]) for x in r["risk"]], [(1, 2), (2, 3)])
        self.assertEqual(r["lower_zone"], "Muito baixa")

    def test_projecao_de_tempo(self):
        r = sim.simulate([2, 0, 0, 0, 1], target=47, pace=2, period="semana", today=date(2026, 10, 10))
        self.assertEqual(r["needed"], 9)
        self.assertEqual(r["plan"]["periods"], 5)           # 9 / 2 por semana
        self.assertEqual(r["plan"]["days"], 35)
        self.assertEqual(r["plan"]["duration"], "1 mês")
        self.assertEqual(r["plan"]["date"], "14/11/2026")
        self.assertEqual([p["pace"] for p in r["paces"]], [2, 5, 10])
        self.assertTrue(r["paces"][0]["active"])

    def test_meta_invalida_volta_para_o_padrao(self):
        r = sim.simulate([2, 0, 0, 0, 1], target=20)
        self.assertEqual(r["target"], 39)
        r = sim.simulate([2, 0, 0, 0, 1], target=999, period="ano", pace=-3)
        self.assertEqual((r["target"], r["period"], r["pace"]), (39, "semana", 1))

    def test_nota_maxima(self):
        r = sim.simulate([22, 0, 0, 0, 0])
        self.assertTrue(r["max"])
        self.assertIsNone(r["target"])
        self.assertEqual(r["needed"], 0)
        self.assertEqual(r["growth"], [])
        self.assertEqual(r["zone"]["name"], "Excelente")
        self.assertEqual([x["count"] for x in r["risk"]], [3, 3, 5])  # para cair a 4,6

    def test_faixa_mais_baixa_nao_tem_risco(self):
        r = sim.simulate([0, 0, 0, 0, 3])
        self.assertEqual(r["zone"]["name"], "Muito baixa")
        self.assertEqual(r["risk"], [])
        self.assertIsNone(r["lower_zone"])

    def test_sem_avaliacoes(self):
        with self.assertRaises(sim.SimulatorError):
            sim.simulate([0, 0, 0, 0, 0])

    def test_duracao(self):
        self.assertEqual(sim.duration(3), "3 dias")
        self.assertEqual(sim.duration(14), "2 semanas")
        self.assertEqual(sim.duration(45), "1 mês e 2 semanas")
        self.assertEqual(sim.duration(64), "2 meses")
        self.assertEqual(sim.duration(0), "menos de 1 dia")


if __name__ == "__main__":
    unittest.main()
