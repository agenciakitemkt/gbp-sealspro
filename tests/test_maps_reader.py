"""Leitor da captura do Google Maps (fontes A a D) sobre fixtures anonimizadas de tests/fixtures/pre/maps/.

Regra testada dos dois lados: fonte nao coletada (ou ilegivel) = nao avaliado com aviso; fonte coletada e dado
inexistente = 0, como no original. O leitor nunca levanta excecao por causa do conteudo da captura."""

import copy
import glob
import json
import os
import re
import unittest
from datetime import datetime, timezone

from collector_pre import maps_reader as mr
from scoring.pre import analyze

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pre", "maps")
NOW = "2026-10-09T23:00:00+00:00"


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def capture(label="A", **sources):
    return {"capturedAt": NOW, "place": load(f"place_{label}.json"), **sources}


def items(profile):
    return {i["id"]: i for i in analyze(profile)["items"]}


def status(profile, item_id):
    return items(profile)[item_id]["status"]


def score(profile, item_id):
    return items(profile)[item_id]["score"]


def wrb(inner):
    body = json.dumps([["wrb.fr", "hspqX", json.dumps(inner)]])
    return f")]}}'\n\n{len(body)}\n{body}\n"


def photo_inner(page=0):
    text = load("photos_A.json")[page]
    return mr.batchexecute(text)


OWNER, VIDEO, PANO = "CgIgARICEAE=", "CgIgARICCAQ=", "CgIgARICCAI="


def photo_page(items, end, code=None):
    """Pagina da galeria; code = categoria em [13] (as categorias pedidas pela aba controlada so valem com ela)."""
    inner = photo_inner(0)
    inner[0] = items
    inner[10] = end
    if code:
        inner[13] = [code]
    return wrb(inner)


def sphere_item(street_view=True):
    """Foto 360: o panorama do Street View (sem bizbuilder) ou uma foto esferica do proprietario. Marca: [21][2][1] = 2."""
    base = photo_item(owner=not street_view)
    base[21][2][1] = 2
    return base


def photo_item(owner=True, video=False, date=(2026, 9, 1, 12)):
    """Item da galeria a partir dos modelos reais anonimizados: foto do proprietario, video ou foto de cliente."""
    page1, page2 = photo_inner(0)[0], photo_inner(1)[0]
    base = copy.deepcopy(page1[1] if video else page1[0] if owner else page2[-1])
    base[21][6][8] = list(date)
    if not owner:
        self_check = json.dumps(base)
        assert "bizbuilder:" not in self_check
    return base


# ---------------------------------------------------------------------------

class FonteATest(unittest.TestCase):
    def setUp(self):
        self.p = mr.read_capture(capture("A"))

    def test_campos_do_local(self):
        loc = self.p["location"]
        self.assertTrue(loc["name"].startswith("Negócio Exemplo A"))
        self.assertEqual(loc["phone"], "(00) 00000-0000")
        self.assertEqual(loc["website"], "https://example.com/")
        self.assertTrue(loc["verified"])
        self.assertEqual(loc["id"], "1")             # CID: hexadecimal depois de ':' em decimal
        self.assertEqual(loc["categories"][0], loc["category"])
        self.assertTrue(loc["hours"])
        self.assertTrue(loc["logoUrl"])

    def test_avaliacoes_vem_da_fonte_a(self):
        r = self.p["reviews"]
        self.assertEqual((r["count"], r["average"]), (464, 4.9))
        self.assertEqual(r["starDistribution"], [449, 6, 3, 1, 5])  # 5 -> 1 (a fonte manda 1 -> 5)

    def test_nao_verificado_e_site_de_rede_social(self):
        p = mr.read_capture(capture("C"))
        self.assertFalse(p["location"]["verified"])
        self.assertEqual(score(p, "verified"), 0)
        self.assertEqual(score(p, "website"), 50)
        self.assertEqual(score(p, "phone"), 0)        # coletado e sem telefone = 0

    def test_sem_site(self):
        self.assertEqual(score(mr.read_capture(capture("D")), "website"), 0)

    def test_aceita_texto_com_prefixo(self):
        text = ")]}'\n" + json.dumps(load("place_A.json"))
        self.assertEqual(mr.read_capture({"capturedAt": NOW, "place": text})["location"]["id"], "1")

    def test_fontes_nao_capturadas_ficam_nao_avaliadas(self):
        # 360 vem da categoria da galeria (photos360); redes sociais, da busca do Google (socialLinks)
        for item in ("photos_360", "social_links"):
            self.assertEqual(status(self.p, item), "unavailable", item)


class FonteBTest(unittest.TestCase):
    def test_amostra(self):
        p = mr.read_capture(capture("B", reviews=load("reviews_B.json")))
        s = p["reviews"]["sample"]
        self.assertEqual((s["size"], s["unanswered"], s["withText"]), (60, 58, 24))
        self.assertEqual(p["reviews"]["count"], 3892)  # sempre da fonte A, nunca o tamanho da amostra
        self.assertEqual(p["reviews"]["lastReviewDays"], 0)
        self.assertEqual(p["warnings"], [])
        for item in ("last_review", "reviews_trend", "reviews_unanswered", "reviews_with_text"):
            self.assertNotEqual(status(p, item), "unavailable", item)

    def test_amostra_de_menor_nota_e_ultima_avaliacao_das_mais_recentes(self):
        pages = load("reviews_B.json")
        recent = mr.read_capture(capture("B", reviews=pages))
        # menor nota: so as 2 ultimas paginas, fora de ordem de data (como vem ordenada por nota)
        p = mr.read_capture(capture("B", reviews=pages[:1], reviewsLowest=list(reversed(pages[-2:]))))
        self.assertEqual(p["reviews"]["sample"]["size"], 20)
        self.assertEqual(p["reviews"]["lastReviewDays"], recent["reviews"]["lastReviewDays"])
        dates = [r["at"] for pg in pages[-2:] for r in mr.read_reviews([pg], mr.Reading())]
        newest_first = sorted(dates, reverse=True)
        ratings = {r["at"]: r["rating"] for pg in pages[-2:] for r in mr.read_reviews([pg], mr.Reading())}
        self.assertEqual(p["reviews"]["sample"]["ratings"], [ratings[d] for d in newest_first])
        self.assertNotIn("reviews_trend", p["notCollected"])

    def test_captura_antiga_sem_menor_nota_usa_as_mais_recentes(self):
        p = mr.read_capture(capture("B", reviews=load("reviews_B.json")))
        self.assertEqual(p["reviews"]["sample"]["size"], 60)

    def test_menor_nota_vazia_nao_avalia_a_amostra(self):
        p = mr.read_capture(capture("B", reviews=load("reviews_B.json")[:1], reviewsLowest=[]))
        self.assertIsNone(p["reviews"]["sample"])
        for item in ("reviews_unanswered", "reviews_with_text", "reviews_trend"):
            self.assertEqual(status(p, item), "unavailable", item)
        self.assertTrue(p["warnings"])

    def test_amostra_fica_nas_100_mais_recentes(self):
        pages = load("reviews_B.json")
        p = mr.read_capture(capture("B", reviews=pages * 3))  # 180 avaliacoes (repetidas): so as 100 primeiras contam
        self.assertEqual(p["reviews"]["sample"]["size"], 100)
        self.assertEqual(len(p["reviews"]["sample"]["ratings"]), 100)

    def test_entrega_a_amostra_ordenada_sem_decidir_o_n(self):
        p = mr.read_capture(capture("B", reviews=load("reviews_B.json")))
        s = p["reviews"]["sample"]
        self.assertEqual(len(s["ratings"]), 60)       # da mais recente para a mais antiga, como veio
        self.assertNotIn("recentSize", s)             # N da tendencia e regra de nota: fica no motor
        self.assertNotIn("recentAverage", s)

    def test_n_da_tendencia_usa_o_total_da_fonte_a(self):
        place = load("place_B.json")
        place[6][4][8] = 120          # N = 12 pelo config do motor
        p = mr.read_capture({"capturedAt": NOW, "place": place, "reviews": load("reviews_B.json")})
        self.assertEqual(items(p)["reviews_trend"]["message"]["vars"]["recentSize"], 12)

    def test_fora_de_ordem_nao_avalia_ultima_avaliacao_nem_tendencia(self):
        pages = load("reviews_B.json")
        p = mr.read_capture(capture("B", reviews=pages[::-1]))
        self.assertEqual(status(p, "last_review"), "unavailable")
        self.assertEqual(status(p, "reviews_trend"), "unavailable")
        self.assertNotEqual(status(p, "reviews_unanswered"), "unavailable")
        self.assertTrue(any("mais recente para a mais antiga" in w for w in p["warnings"]))

    def test_nao_coletada_e_nao_avaliado(self):
        p = mr.read_capture(capture("B"))
        self.assertEqual(status(p, "last_review"), "unavailable")
        self.assertIsNone(p["reviews"]["sample"])

    def test_zero_avaliacoes_na_fonte_a_e_0_mesmo_sem_a_fonte_b(self):
        place = load("place_B.json")
        place[6][4][8] = 0
        p = mr.read_capture({"capturedAt": NOW, "place": place})
        self.assertEqual(p["reviews"]["count"], 0)
        self.assertEqual(score(p, "last_review"), 0)
        self.assertEqual(score(p, "reviews_count"), 0)
        self.assertEqual(score(p, "reviews_average"), 0)


class FonteCTest(unittest.TestCase):
    def test_galeria_lida_inteira(self):
        p = mr.read_capture(capture("A", photos=load("photos_A.json")))
        self.assertEqual(p["media"]["lastOwnerPhotoDays"], 7)   # 29/09 a 09/10: 10 dias = "1 semana" = 7
        self.assertEqual(p["media"]["videos"], 14)
        self.assertEqual(p["warnings"], [])

    def test_sem_categoria_do_proprietario_e_0_mesmo_sem_a_fonte_c(self):
        p = mr.read_capture(capture("C"))
        self.assertEqual(score(p, "last_owner_photo"), 0)
        self.assertEqual(score(p, "videos"), 0)                  # sem a categoria "Videos" = 0

    def test_com_categoria_e_sem_a_fonte_c_e_nao_avaliado(self):
        p = mr.read_capture(capture("A"))
        self.assertEqual(status(p, "last_owner_photo"), "unavailable")
        self.assertEqual(status(p, "videos"), "unavailable")
        self.assertEqual(p["warnings"], [])                      # nao coletar nao e leitor desatualizado

    def test_tres_videos_resolvem_mesmo_sem_ler_tudo(self):
        page = photo_page([photo_item(video=True)] * 3 + [photo_item()] * 17, end=False)
        p = mr.read_capture(capture("A", photos=[page]))
        self.assertEqual(p["media"]["videos"], 3)
        self.assertEqual(score(p, "videos"), 100)

    def test_menos_de_3_videos_sem_ler_tudo_e_nao_avaliado(self):
        page = photo_page([photo_item(video=True)] * 2 + [photo_item()] * 18, end=False)
        p = mr.read_capture(capture("A", photos=[page]))
        self.assertEqual(status(p, "videos"), "unavailable")
        self.assertTrue(any("vídeos não avaliados" in w for w in p["warnings"]))

    def test_menos_de_3_videos_com_tudo_lido_e_final(self):
        page = photo_page([photo_item(video=True)] * 2 + [photo_item()] * 3, end=True)
        p = mr.read_capture(capture("A", photos=[page]))
        self.assertEqual(score(p, "videos"), 50)

    def test_foto_antiga_sem_ler_tudo_e_nao_avaliado(self):
        page = photo_page([photo_item(date=(2026, 1, 5, 9))] * 20, end=False)
        p = mr.read_capture(capture("A", photos=[page]))
        self.assertEqual(status(p, "last_owner_photo"), "unavailable")

    def test_foto_recente_sem_ler_tudo_ja_e_final(self):
        page = photo_page([photo_item(date=(2026, 10, 1, 9))] * 20, end=False)
        p = mr.read_capture(capture("A", photos=[page]))
        self.assertEqual(p["media"]["lastOwnerPhotoDays"], 7)

    def test_so_foto_de_cliente_com_tudo_lido_vale_0(self):
        page = photo_page([photo_item(owner=False)] * 3, end=True)
        p = mr.read_capture(capture("A", photos=[page]))
        self.assertEqual(score(p, "last_owner_photo"), 0)
        self.assertTrue(p["warnings"])


class PostagensTest(unittest.TestCase):
    """Fonte A, [6][122][1]: postagens com a data de criacao em [2][0] (segundos Unix)."""

    def test_ultima_postagem(self):
        p = mr.read_capture(capture("A"))
        self.assertEqual(p["posts"], {"count": 5, "lastPostDays": 2})   # 07/10 a 09/10
        self.assertEqual(score(p, "last_post"), 100)
        self.assertNotIn("last_post", p["notCollected"])

    def test_sem_postagens_vale_0(self):
        p = mr.read_capture(capture("C"))
        self.assertEqual(p["posts"], {"count": 0, "lastPostDays": None})
        self.assertEqual(score(p, "last_post"), 0)

    def test_postagem_antiga(self):
        place = load("place_A.json")
        for post in place[6][122][1]:
            post[2][0] = 1785000000  # 25/07/2026: 76 dias antes da captura
        self.assertEqual(score(mr.read_capture({"capturedAt": NOW, "place": place}), "last_post"), 0)

    def test_formato_inesperado_nao_avalia(self):
        place = load("place_A.json")
        place[6][122][1] = "lixo"
        p = mr.read_capture({"capturedAt": NOW, "place": place})
        self.assertIn("last_post", p["notCollected"])
        place[6][122][1] = [["sem", "data"]]
        p = mr.read_capture({"capturedAt": NOW, "place": place})
        self.assertIn("last_post", p["notCollected"])
        self.assertTrue(any("postagens" in w for w in p["warnings"]))

    def test_sem_fonte_a_nao_avalia(self):
        p = mr.read_capture({"capturedAt": NOW, "place": None})
        self.assertIn("last_post", p["notCollected"])


class OutroLocalDoMapaTest(unittest.TestCase):
    """O Maps tambem busca dados de outros locais do mapa: a fonte A so vale se for do perfil aberto."""

    def test_identificador_igual_vale(self):
        ftid = load("place_A.json")[6][10]
        p = mr.read_capture(capture("A", profileFtid=ftid))
        self.assertEqual(p["warnings"], [])
        self.assertEqual(status(p, "business_name"), "good")

    def test_outro_local_nao_vale(self):
        p = mr.read_capture(capture("A", profileFtid="0x0:0x999"))
        self.assertTrue(any("outro local do mapa" in w for w in p["warnings"]))
        for item in ("business_name", "reviews_count", "last_post", "top10_reviews"):
            self.assertEqual(status(p, item), "unavailable", item)

    def test_sem_identificador_na_captura_continua_como_antes(self):
        self.assertEqual(mr.read_capture(capture("A"))["warnings"], [])


def search_review(rid, rating, day, text="", replied=False):
    """Avaliacao no formato da caixa de avaliacoes da busca (GetLocalBoqProxy), com campos ficticios."""
    rv = [None] * 30
    ms = int(datetime(2026, 9, day, 12, tzinfo=timezone.utc).timestamp() * 1000)
    rv[1], rv[2], rv[5], rv[27] = rating, ["x", None, str(ms)], rid, text
    rv[4] = [None, "x", "resposta"] if replied else None
    return rv


def search_page(reviews, token=""):
    return ")]}'\n\n" + json.dumps([[None], [None] * 10 + [[None, None, reviews, None, None, None, token]]])


class EscalaDoGbpCheckTest(unittest.TestCase):
    def test_dias_na_escala_do_texto_do_google(self):
        for exato, gbp in ((0, 0), (6, 6), (10, 7), (20, 14), (29, 28), (38, 30), (65, 60), (169, 150), (364, 360),
                           (806, 730), (None, None)):
            self.assertEqual(mr.as_google_days(exato), gbp, exato)


class AmostraDaBuscaTest(unittest.TestCase):
    """Amostra como a do GBP Check: menor nota + mais recentes da caixa de avaliacoes da busca, sem repetir."""

    def test_uniao_sem_repetir_e_campos(self):
        lowest = [search_page([search_review("a", 1, 5, "ruim"), search_review("b", 2, 6, "", True)], "T"),
                  search_page([search_review("c", 5, 1, "ok", True)])]
        newest = [search_page([search_review("d", 5, 20, "bom", True), search_review("a", 1, 5, "ruim")])]
        p = mr.read_capture(capture("B", reviewsSearch={"lowest": lowest, "newest": newest}))
        s = p["reviews"]["sample"]
        self.assertEqual((s["size"], s["unanswered"], s["withText"], s["average"]), (4, 1, 3, 3.25))
        self.assertEqual(s["ratings"], [5, 2, 1, 5])  # da mais recente para a mais antiga

    def test_tem_prioridade_sobre_as_amostras_do_maps(self):
        search = {"lowest": [search_page([search_review("a", 3, 5)])], "newest": []}
        p = mr.read_capture(capture("B", reviews=load("reviews_B.json"), reviewsLowest=load("reviews_B.json"),
                                    reviewsSearch=search))
        self.assertEqual(p["reviews"]["sample"]["size"], 1)
        self.assertIsNotNone(p["reviews"]["lastReviewDays"])  # a ultima avaliacao continua das mais recentes do Maps

    def test_perfil_grande_usa_5_paginas_de_cada_lista_e_pequeno_usa_todas(self):
        newest = [search_page([search_review(f"n{i}", 5, 1 + i)]) for i in range(8)]
        lowest = [search_page([search_review(f"l{i}", 1, 1 + i)]) for i in range(7)]
        grande = mr.read_capture(capture("B", reviewsSearch={"lowest": lowest, "newest": newest}))  # 464 avaliacoes
        self.assertEqual(grande["reviews"]["sample"]["size"], 10)
        cap = capture("B", reviewsSearch={"lowest": lowest, "newest": newest})
        cap["place"][6][4][8] = 64  # perfil pequeno: o GBP Check le todas
        self.assertEqual(mr.read_capture(cap)["reviews"]["sample"]["size"], 15)

    def test_formato_inesperado_cai_na_amostra_do_maps_com_aviso(self):
        for junk in ("x", {"lowest": "x", "newest": []}, {"lowest": ["<html>"], "newest": []},
                     {"lowest": [search_page([[None, 9]])], "newest": []}):
            p = mr.read_capture(capture("B", reviews=load("reviews_B.json"), reviewsSearch=junk))
            self.assertEqual(p["reviews"]["sample"]["size"], 60, junk)
            self.assertTrue(p["warnings"], junk)


class RedesSociaisTest(unittest.TestCase):
    """Bloco "Perfis" do painel da busca do Google, lido pela extensao no clique do botao da busca."""

    def test_redes_do_bloco(self):
        p = mr.read_capture(capture("A", socialLinks=[
            "https://www.instagram.com/exemplo/", "https://www.facebook.com/exemplo",
            "https://www.instagram.com/exemplo/", "http://www.linkedin.com/in/exemplo"]))
        self.assertEqual([s["name"] for s in p["location"]["socialLinks"]], ["Instagram", "Facebook", "LinkedIn"])
        self.assertEqual(score(p, "social_links"), 100)
        self.assertNotIn("social_links", p["notCollected"])

    def test_bloco_ausente_vale_50_como_no_original(self):
        p = mr.read_capture(capture("A", socialLinks=[]))
        self.assertEqual(score(p, "social_links"), 50)

    def test_redirecionamento_do_google_e_dominio_desconhecido(self):
        p = mr.read_capture(capture("A", socialLinks=[
            "https://www.google.com/url?q=https://www.youtube.com/@exemplo&sa=U",
            "https://linktr.ee/exemplo", "javascript:alert(1)", "/relativo"]))
        self.assertEqual(p["location"]["socialLinks"], [
            {"name": "YouTube", "url": "https://www.youtube.com/@exemplo"},
            {"name": "linktr.ee", "url": "https://linktr.ee/exemplo"}])

    def test_sem_socialLinks_nao_avalia(self):
        p = mr.read_capture(capture("A"))
        self.assertEqual(status(p, "social_links"), "unavailable")

    def test_formato_inesperado_nao_avalia_com_aviso(self):
        for junk in ("x", 7, {"a": 1}, [None], [["x"]]):
            p = mr.read_capture(capture("A", socialLinks=junk))
            self.assertEqual(status(p, "social_links"), "unavailable", junk)
            self.assertTrue(any("redes sociais" in w["message"] if isinstance(w, dict) else "redes sociais" in w
                                for w in p["warnings"]), junk)

    def test_sem_fonte_a_nao_avalia(self):
        p = mr.read_capture({"capturedAt": NOW, "socialLinks": ["https://www.instagram.com/exemplo/"]})
        self.assertEqual(status(p, "social_links"), "unavailable")


class CategoriasPeloCodigoTest(unittest.TestCase):
    """As categorias da galeria valem pelo codigo da fonte A, nao pelo nome (que muda com o idioma do Maps)."""

    def place_with(self, names_and_codes):
        place = load("place_A.json")
        template = place[6][171][0][0]
        place[6][171][0] = [[code, *template[1:2], name, *template[3:]] for code, name in names_and_codes]
        return place

    def test_maps_em_ingles_continua_reconhecendo(self):
        place = self.place_with([("CgIgAQ==", "All"), ("CgIgARICEAE=", "From the owner"), ("CgIgARICCAQ=", "Videos")])
        p = mr.read_capture({"capturedAt": NOW, "place": place})
        self.assertIn("last_owner_photo", p["notCollected"])   # tem a categoria: sem a fonte C, nao avaliado
        self.assertIn("videos", p["notCollected"])

    def test_codigo_vale_mesmo_com_nome_desconhecido(self):
        place = self.place_with([("CgIgARICEAE=", "Propietario"), ("CgIgARICCAQ=", "Vidéos")])
        p = mr.read_capture({"capturedAt": NOW, "place": place})
        self.assertIn("last_owner_photo", p["notCollected"])
        self.assertIn("videos", p["notCollected"])

    def test_nome_em_portugues_ou_ingles_vale_sem_codigo(self):
        place = self.place_with([("", "Do proprietário"), ("x", "videos")])
        p = mr.read_capture({"capturedAt": NOW, "place": place})
        self.assertIn("last_owner_photo", p["notCollected"])
        self.assertIn("videos", p["notCollected"])

    def test_sem_as_categorias_continua_0(self):
        place = self.place_with([("CgIgAQ==", "All"), ("CgIgARICCAI=", "Street View & 360°")])
        p = mr.read_capture({"capturedAt": NOW, "place": place})
        self.assertEqual((score(p, "last_owner_photo"), score(p, "videos")), (0, 0))


class CategoriasDaGaleriaTest(unittest.TestCase):
    """Fase 2: a extensao abre "Do proprietario" e "Videos" (formato das paginas igual ao da "Mais recentes": hipotese
    a conferir na primeira captura real)."""

    def test_categoria_do_proprietario_lida_inteira_resolve_mesmo_com_foto_antiga(self):
        page = photo_page([photo_item(date=(2026, 1, 5, 9))] * 5, end=True, code=OWNER)
        p = mr.read_capture(capture("A", photosOwner=[page]))
        self.assertEqual(p["media"]["lastOwnerPhotoDays"], 270)
        self.assertNotIn("last_owner_photo", p["notCollected"])

    def test_na_categoria_do_proprietario_todo_item_conta(self):
        page = photo_page([photo_item(owner=False, date=(2026, 10, 1, 9))], end=True, code=OWNER)
        p = mr.read_capture(capture("A", photosOwner=[page]))
        self.assertEqual(p["media"]["lastOwnerPhotoDays"], 7)

    def test_categoria_tem_prioridade_sobre_a_mais_recentes(self):
        recent = photo_page([photo_item(date=(2026, 10, 8, 9))] * 20, end=False)
        owner = photo_page([photo_item(date=(2026, 9, 1, 9))] * 3, end=True, code=OWNER)
        p = mr.read_capture(capture("A", photos=[recent], photosOwner=[owner]))
        self.assertEqual(p["media"]["lastOwnerPhotoDays"], 30)

    def test_categoria_videos(self):
        done = photo_page([photo_item(video=True)] * 2, end=True, code=VIDEO)
        self.assertEqual(mr.read_capture(capture("A", photosVideos=[done]))["media"]["videos"], 2)
        partial = photo_page([photo_item(video=True)] * 2 + [photo_item()] * 18, end=False, code=VIDEO)
        p = mr.read_capture(capture("A", photosVideos=[partial]))
        self.assertIn("videos", p["notCollected"])

    def test_categoria_inexistente_na_fonte_a_vale_0_mesmo_capturada(self):
        videos = photo_page([photo_item(video=True)] * 4, end=True, code=VIDEO)
        owner = photo_page([photo_item(video=True)] * 4, end=True, code=OWNER)
        p = mr.read_capture(capture("C", photosVideos=[videos], photosOwner=[owner]))
        self.assertEqual((p["media"]["videos"], p["media"]["lastOwnerPhotoDays"]), (0, None))
        self.assertEqual(score(p, "last_owner_photo"), 0)


class Fotos360Test(unittest.TestCase):
    """Categoria "Street View e 360°" da galeria (0.4.1). Conta os itens esfericos, com o panorama do Street View,
    como o original: so o Street View (1) = 0; 2 ou mais = 100 (conferido em dois perfis, 2026-10-10)."""

    def test_so_o_street_view_vale_0(self):
        p = mr.read_capture(capture("A", photos360=[photo_page([sphere_item()], end=True, code=PANO)]))
        self.assertEqual(p["media"]["photos360"], 1)
        self.assertEqual(score(p, "photos_360"), 0)
        self.assertNotIn("photos_360", p["notCollected"])

    def test_street_view_e_mais_uma_vale_100(self):
        page = photo_page([sphere_item(street_view=False), sphere_item()], end=True, code=PANO)
        p = mr.read_capture(capture("A", photos360=[page]))
        self.assertEqual((p["media"]["photos360"], score(p, "photos_360")), (2, 100))

    def test_so_contam_os_itens_esfericos(self):
        page = photo_page([sphere_item(), photo_item(), photo_item(owner=False)], end=True, code=PANO)
        self.assertEqual(mr.read_capture(capture("A", photos360=[page]))["media"]["photos360"], 1)

    def test_categoria_sem_marca_esferica_nao_avalia_com_aviso(self):
        p = mr.read_capture(capture("A", photos360=[photo_page([photo_item()] * 2, end=True, code=PANO)]))
        self.assertEqual(status(p, "photos_360"), "unavailable")
        self.assertTrue(p["warnings"])

    def test_lida_pela_metade_com_menos_de_2_nao_avalia(self):
        page = photo_page([sphere_item()] + [photo_item()] * 19, end=False, code=PANO)
        self.assertEqual(status(mr.read_capture(capture("A", photos360=[page])), "photos_360"), "unavailable")
        page = photo_page([sphere_item()] * 2 + [photo_item()] * 18, end=False, code=PANO)
        self.assertEqual(score(mr.read_capture(capture("A", photos360=[page])), "photos_360"), 100)

    def test_sem_a_categoria_na_fonte_a_vale_0(self):
        cap = capture("A")
        cap["place"][6][171][0] = [c for c in cap["place"][6][171][0] if "360" not in c[2]]
        p = mr.read_capture(cap)
        self.assertEqual((p["media"]["photos360"], score(p, "photos_360")), (0, 0))

    def test_paginas_do_visualizador_do_street_view_ficam_de_fora(self):
        # O visualizador busca panoramas vizinhos pelo mesmo hspqX, sem a categoria em [13]: nao contam
        viewer = photo_inner(0)
        viewer[0], viewer[10] = [sphere_item()] * 4, False
        del viewer[11:]
        p = mr.read_capture(capture("A", photos360=[wrb(viewer), photo_page([sphere_item()], end=True, code=PANO)]))
        self.assertEqual((p["media"]["photos360"], score(p, "photos_360")), (1, 0))
        p = mr.read_capture(capture("A", photos360=[wrb(viewer)]))
        self.assertEqual(status(p, "photos_360"), "unavailable")
        self.assertTrue(p["warnings"])

    def test_pagina_de_outra_categoria_fica_de_fora(self):
        other = photo_page([photo_item(owner=False)] * 5, end=True, code="CgIgAQ==")
        owner = photo_page([photo_item(date=(2026, 9, 1, 9))], end=True, code=OWNER)
        p = mr.read_capture(capture("A", photosOwner=[other, owner]))
        self.assertEqual(p["media"]["lastOwnerPhotoDays"], 30)

    def test_categoria_nao_capturada_nao_avalia(self):
        self.assertEqual(status(mr.read_capture(capture("A")), "photos_360"), "unavailable")


class FonteDTest(unittest.TestCase):
    def test_formatos_da_resposta_da_busca(self):
        payload = load("search_A.json")
        text = json.dumps(payload)
        for page in (text, ")]}'\n" + text, text + '/*""*/', {"d": ")]}'\n" + text},
                     json.dumps({"c": 0, "d": ")]}'\n" + text}) + '/*""*/'):
            p = mr.read_capture(capture("A", search=[page]))
            self.assertEqual(p["competitors"]["count"], 3, str(page)[:40])


    def test_concorrentes_sem_anuncio(self):
        p = mr.read_capture(capture("A", search=[load("search_A.json")]))
        c = p["competitors"]
        self.assertEqual(c["count"], 3)           # 4 resultados, 1 anuncio
        self.assertEqual(score(p, "top10_reviews"), 100)
        self.assertEqual(score(p, "above_segment_average"), 100)

    def results(self, counts, own=None):
        out = []
        for n, k in enumerate(counts):
            p = [None] * 12
            p[10] = f"0x0:0x{own if n == 0 and own else 100 + n:x}"
            p[4] = [None] * 7 + [4.5, k]
            out.append([None, p, None, None, None, None, None])
        return [None] * 64 + [out]

    def test_top_10_e_media(self):
        counts = mr.read_search([self.results([50] * 10 + [5])], "1", mr.Reading())
        self.assertEqual(mr._competitors(counts, 40)["inTop10ByReviews"], False)  # 10 com mais avaliacoes
        self.assertEqual(mr._competitors(counts, 50)["inTop10ByReviews"], True)   # empate conta a favor
        self.assertEqual(mr._competitors(counts, 0)["averageReviews"], round(505 / 11, 1))

    def test_so_concorrentes_de_categoria_parecida(self):
        page = self.results([10, 20, 30, 40, 50])
        for entry, cat in zip(page[64], ["Oftalmologista", "Clínica oftalmológica", "Médico", "Ótica", None]):
            entry[1].extend([None] * 2)
            entry[1][13] = [cat] if cat else None
        counts = mr.read_search([page], "1", mr.Reading(), ["Oftalmologista"])
        self.assertEqual(counts, [10, 20])
        self.assertEqual(mr.read_search([page], "1", mr.Reading()), [10, 20, 30, 40, 50])  # sem categorias: todos

    def test_proprio_negocio_e_repetidos_ficam_fora(self):
        page = self.results([999, 10], own=1)
        counts = mr.read_search([page, page], "1", mr.Reading())
        self.assertEqual(counts, [10])

    def test_pagina_ilegivel_pula_so_ela(self):
        p = mr.read_capture(capture("A", search=[load("search_A.json"), "lixo", {"x": 1}]))
        self.assertEqual(p["competitors"]["count"], 3)
        self.assertTrue(any("fonte D" in w for w in p["warnings"]))
        self.assertNotIn("top10_reviews", p["notCollected"])

    def test_busca_vazia_fica_fora_da_nota(self):
        p = mr.read_capture(capture("A", search=[[None] * 64 + [[]]]))
        self.assertEqual(status(p, "top10_reviews"), "unavailable")

    def test_nao_coletada(self):
        self.assertIsNone(mr.read_capture(capture("A"))["competitors"])


class FormatoInesperadoTest(unittest.TestCase):
    """Lixo em qualquer fonte: nunca excecao; os itens da fonte ficam nao avaliados, com aviso."""

    GARBAGE = (None, "lixo", 7, [], {}, [1, 2], [[None]], ")]}'\n{nao e json")

    def test_nunca_levanta_excecao(self):
        for junk in self.GARBAGE:
            for key in ("place", "reviews", "photos", "search"):
                cap = capture("A", reviews=load("reviews_B.json"), photos=load("photos_A.json"),
                              search=[load("search_A.json")])
                cap[key] = junk if key == "place" else ([junk] if junk is not None else None)
                analyze(mr.read_capture(cap))
        for cap in (None, {}, [], "x", {"capturedAt": "ontem"}):
            analyze(mr.read_capture(cap))

    def test_local_ilegivel(self):
        p = mr.read_capture({"capturedAt": NOW, "place": {"x": 1}})
        self.assertEqual({i["status"] for i in analyze(p)["items"]}, {"unavailable"})
        self.assertTrue(any("fonte A" in w for w in p["warnings"]))

    def test_campo_em_formato_errado_so_tira_o_item(self):
        place = load("place_A.json")
        place[6][4][8] = "muitas"
        place[6][178] = [[{"x": 1}]]
        p = mr.read_capture({"capturedAt": NOW, "place": place})
        self.assertEqual(status(p, "reviews_count"), "unavailable")
        self.assertEqual(status(p, "phone"), "unavailable")
        self.assertEqual(status(p, "logo"), "good")
        self.assertTrue(any("total de avaliações" in w for w in p["warnings"]))

    def test_paginas_ilegiveis(self):
        p = mr.read_capture(capture("B", reviews=["lixo"]))
        self.assertEqual(status(p, "last_review"), "unavailable")
        self.assertTrue(any("fonte B" in w for w in p["warnings"]))
        p = mr.read_capture(capture("A", photos=["lixo"]))
        self.assertEqual(status(p, "videos"), "unavailable")
        self.assertTrue(any("fonte C" in w for w in p["warnings"]))
        p = mr.read_capture(capture("A", search=[{"x": 1}]))
        self.assertEqual(status(p, "top10_reviews"), "unavailable")
        self.assertTrue(any("fonte D" in w for w in p["warnings"]))

    def test_sem_data_da_captura(self):
        p = mr.read_capture({"place": load("place_A.json")})
        self.assertTrue(any("capturedAt" in w for w in p["warnings"]))


class CapturaCompletaTest(unittest.TestCase):
    def test_perfil_completo_passa_pelo_motor(self):
        p = mr.read_capture(capture("A", photos=load("photos_A.json"), search=[load("search_A.json")]))
        r = analyze(p)
        for i in r["items"]:
            i["message"]["template"].format(**i["message"]["vars"])
        self.assertEqual(datetime.fromisoformat(r["analyzedAt"]), datetime(2026, 10, 9, 23, tzinfo=timezone.utc))
        unavailable = {i["id"] for i in r["items"] if i["status"] == "unavailable"}
        self.assertEqual(unavailable, {"photos_360", "social_links", "last_review", "reviews_trend",
                                       "reviews_unanswered", "reviews_with_text"})


class FixturesAnonimizadasTest(unittest.TestCase):
    def test_sem_dado_real(self):
        for path in glob.glob(os.path.join(FIX, "*.json")):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for url in re.findall(r"https?:(?:\\\\?/){2}[^\"\\\\\s]+", text):
                self.assertRegex(url, r"(example\.com|instagram\.com\\*/exemplo)", path)
            for phone in re.findall(r"\(\d\d\) ?\d{4,5}-\d{4}", text):
                self.assertEqual(phone, "(00) 00000-0000", path)
            for ftid in re.findall(r"0x[0-9a-f]+:0x[0-9a-f]+", text):
                self.assertTrue(ftid.startswith("0x0:"), (path, ftid))
            self.assertNotRegex(text, r"(?<![\d.])-?\d{2,3}\.\d{5,}(?![\de])", path)   # coordenadas (lat, lng)
            self.assertNotRegex(text, r"\bChIJ(?!-exemplo)", path)   # place_id real


if __name__ == "__main__":
    unittest.main()
