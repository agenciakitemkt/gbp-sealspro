"""Calibracao do motor da Pre Analise: TODOS os limites e pontos de curva dos 20 itens ficam aqui.

Mesmos estados da Completa (scoring/config.py):
  MEDIDO   - varios pontos do original confirmam a regra
  PARCIAL  - a faixa e conhecida, mas o limite exato nao
  HIPOTESE - poucos pontos; valor escolhido por nos

Fonte dos pontos: as 54 pre analises guardadas no GBP Check (data/reference/pre_analises_original.json, lidas em
2026-10-09). `observed` traz os pontos medidos (valor bruto -> nota do original) que sustentam cada regra.

O status por nota e a formula da nota geral sao os da Completa (scoring/base.py, com BAD_BELOW, GOOD_AT e OVERALL
de scoring/config.py): conferem nos 54 casos.

Curvas em degraus (`steps`): lista de (limite_inclusivo, nota), lida em ordem; acima do ultimo limite vale `beyond`.
Curvas "quanto mais, melhor" (`floors`): lista de (minimo, nota) do maior para o menor; abaixo de todos vale `below`.
"""

from scoring.config import HIPOTESE, MEDIDO, PARCIAL

CONFIG = {
    # ---- perfil ----
    "business_name": {"estado": PARCIAL, "max": 98, "over_score": 50,
                      "observed": "ate 82 caracteres = 100 (53 casos); 102 = 50. Entre 83 e 101 nao ha medida; "
                                  "98 vem da mensagem do original"},
    "phone": {"estado": MEDIDO, "observed": "tem = 100 (52), nao tem = 0 (2)"},
    "website": {"estado": MEDIDO, "social_score": 50,
                # Primeiro nome do endereco (sem www): instagram.com.br tambem conta. So Instagram foi medido.
                "social_names": ["instagram", "facebook", "fb", "tiktok", "linkedin", "twitter", "x", "youtube",
                                 "threads", "whatsapp", "wa"],
                "observed": "dominio proprio = 100 (45, inclui wixsite e pages.net.br); Instagram = 50 (4); "
                            "sem site = 0 (5). As outras redes da lista sao hipotese"},
    "hours": {"estado": MEDIDO, "observed": "definido = 100 (52), nao = 0 (2)"},
    "description": {"estado": PARCIAL, "steps": [(0, 0), (49, 40), (99, 70), (119, 80)], "beyond": 100,
                    "observed": "0 = 0; 23 a 48 = 40; 54 a 99 = 70; 101 e 108 = 80; 122 ou mais = 100. "
                                "Sem medida: 49 a 53, 100 e 109 a 121"},
    "logo": {"estado": MEDIDO, "observed": "tem = 100 (51), nao = 0 (3)"},
    "verified": {"estado": MEDIDO, "observed": "verificado = 100 (51), nao = 0 (3)"},
    "social_links": {"estado": MEDIDO, "none_score": 50,
                     "observed": "1 ou mais = 100 (51); nenhuma = 50 (3), e nao 0"},

    # ---- postagens e midia ----
    "last_post": {"estado": PARCIAL, "steps": [(15, 100), (30, 50)], "beyond": 0, "no_posts_score": 0,
                  "observed": "sem postagem = 0 (46); 0 a 8 dias = 100; 21 = 50; 74, 106 e 119 = 0. Sem medida: "
                              "9 a 20 e 22 a 73. 15 dias vem da mensagem do original; 30 e hipotese"},
    "last_owner_photo": {"estado": PARCIAL, "steps": [(30, 100), (60, 50)], "beyond": 0, "no_photo_score": 0,
                         "observed": "3 a 30 dias = 100; 31 e 60 = 50; 90 ou mais = 0; sem foto = 0 (5). "
                                     "Sem medida: 61 a 89"},
    "videos": {"estado": PARCIAL, "recommended": 3, "measured": {2: 50},
               "observed": "0 = 0 (44); 2 = 50 (3); 4 = 100 (2). 1 e 3 nao medidos: 1 = 25 (interpolacao) e "
                           "3 = 100 (minimo da mensagem do original) sao hipotese. Na Completa 2 videos dao 66"},
    "photos_360": {"estado": PARCIAL, "min_count": 2,
                   "observed": "0 = 0 (22); 1 = 0 (25); 2 = 100 (1). A spec dizia 'tem = 100', mas com 1 foto 360 "
                               "o original da 0 em todos os casos (hipotese: a primeira e a do Street View, nao do "
                               "proprietario). O limite exato entre 1 e 2 e o unico medido"},

    # ---- avaliacoes ----
    "reviews_count": {"estado": MEDIDO, "recommended": 3, "measured": {1: 50, 2: 66},
                      "observed": "0 = 0; 1 = 50; 2 = 66; 3 ou mais = 100"},
    "reviews_average": {"estado": PARCIAL, "floors": [(4.5, 100), (3.5, 50)], "below": 0, "no_reviews_score": 0,
                        "observed": "sem avaliacao = 0; 1,0 = 0; 3,7 a 4,3 = 50; 4,5 a 5,0 = 100 (1,0 e 3,7 na "
                                    "comparacao ao vivo de 2026-10-10). 4,4 (50) e o corte de 3,5 (abaixo = 0) sao "
                                    "hipotese: o corte fica entre 1,1 e 3,7"},
    "last_review": {"estado": PARCIAL, "steps": [(30, 100), (59, 50)], "beyond": 0, "no_reviews_score": 0,
                    "observed": "0 a 30 dias = 100; 31 = 50; 60 ou mais = 0; sem avaliacao = 0. Sem medida: 32 a 59"},
    "reviews_trend": {"estado": HIPOTESE, "max_drop": 0.5,
                      # N das mais recentes = recent_share% do total de avaliacoes (fonte A), minimo recent_min; se N
                      # passar do tamanho da amostra, usa a amostra inteira. MEDIDO: e o last_fixed_n do original nos
                      # 47 casos com amostra (pre_analises_original.json), inclusive N maior que a amostra.
                      "recent_share": 10, "recent_min": 5, "recent_estado": MEDIDO,
                      "observed": "media das N mais recentes da amostra contra a media da amostra: queda de 0,61 "
                                  "e 1,07 = 0; queda de ate 0,43 = 100; alta = 100. O corte de 0,5 e hipotese"},
    "reviews_unanswered": {"estado": PARCIAL, "good_below": 10, "fair_up_to": 50,
                           "observed": "% sem resposta na amostra: ate 6,8% = 100; 10,5% a 50% = 50; 66,7% ou mais "
                                       "= 0. Sem medida: 6,9% a 10,4% e 50,1% a 66,6%"},
    "reviews_with_text": {"estado": PARCIAL, "floors": [(70, 100), (40, 50)], "below": 0,
                          "observed": "% com comentario na amostra: 70,4% ou mais = 100; 42,9% a 66,7% = 50; 23,8% "
                                      "ou menos = 0. O corte de 40% (entre 23,8% e 42,9%) e hipotese"},

    # ---- concorrentes ----
    "top10_reviews": {"estado": MEDIDO,
                      "observed": "entre os 10 concorrentes com mais avaliacoes = 100, senao 0. Sem concorrentes o "
                                  "original da 100 (5 casos); aqui o item fica fora da nota"},
    "above_segment_average": {"estado": MEDIDO,
                              "observed": "avaliacoes >= media de todos os concorrentes = 100, senao 0. Sem "
                                          "concorrentes o original da 100 (5 casos); aqui o item fica fora da nota"},
}
