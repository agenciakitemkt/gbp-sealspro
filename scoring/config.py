"""Calibracao do motor de nota: TODOS os limites e pontos de curva ficam aqui.

Cada item tem um 'estado':
  MEDIDO   - ponto observado no GBP Check original (CLAUDE.md, secao 5)
  PARCIAL  - parte da curva medida, o resto e hipotese
  HIPOTESE - nada medido alem do caso bom (ou nem isso); valor escolhido por nos

Curvas de contagem: 'measured' = {quantidade: nota} medidos. Entre os pontos medidos, 0 -> 0 e a
quantidade recomendada -> 100, a nota e interpolada linearmente (sem ponto medido = proporcao
atual/recomendado). Notas sao sempre truncadas (66,67 -> 66) e so chegam a 100 no caso bom.
"""

MEDIDO, PARCIAL, HIPOTESE = "medido", "parcial", "hipotese"

# Status derivado da nota (nunca guardado a parte). Hipotese consistente com 0, 50, 66 e 100 observados.
BAD_BELOW = 50   # nota < 50 = fraco
GOOD_AT = 100    # nota == 100 = bom; de 50 a 99 = razoavel

# Nota geral = piso de (bons*100 + razoaveis*50) / itens avaliados (fracos pesam 0). Indisponiveis e itens
# que nao se aplicam ao perfil ficam fora do total. Confirmada no original em 10 locais e na Pre Analise.
OVERALL = {
    "weights": {"good": 100, "fair": 50, "bad": 0},
    "estado": MEDIDO,
}

# Faixas do medidor da nota geral (tela). Lidas do desenho do original, por isso hipotese.
# Observado: 95 = Bom, 75 = Razoavel. Vermelho ate ~60, amarelo de 60 a 80, verde acima de 80.
OVERALL_BANDS = {"estado": HIPOTESE, "fair_from": 60, "good_from": 80}

# Nota de um item binario (tem / nao tem) que falhou. Observado: 0 existe; o motivo exato e hipotese.
BINARY_FAIL_SCORE = 0

CONFIG = {
    # ---- itens binarios ----
    "phone": {"estado": HIPOTESE, "obs": "so o caso bom observado; ausente = 0"},
    "website": {"estado": HIPOTESE, "obs": "so o caso bom observado; ausente = 0"},
    "hours": {"estado": HIPOTESE, "obs": "so o caso bom observado; ausente = 0"},
    "special_hours": {"estado": MEDIDO, "obs": "decisao Fase 0: ao menos um periodo no ano corrente (inicio ou fim)"},
    "logo": {"estado": MEDIDO, "obs": "decisao Fase 0: logo = midia PROFILE (data 1970 ignorada)"},
    "cover": {"estado": HIPOTESE, "obs": "so o caso bom observado; ausente = 0"},
    "services": {"estado": HIPOTESE, "obs": "so o caso bom observado; ausente = 0"},
    "founding_date": {"estado": MEDIDO, "obs": "decisao Fase 0: openInfo.openingDate preenchido"},

    # ---- contagens ----
    "description": {"estado": HIPOTESE, "recommended": 50, "measured": {},
                    "obs": "minimo 50 caracteres (585 = 100); abaixo disso, proporcao"},
    "videos": {"estado": MEDIDO, "recommended": 3, "measured": {1: 50, 2: 66},
               "obs": "0 = 0, 1 = 50, 2 = 66, 3 ou mais = 100 (medido na Completa; a Pre mede 2 videos = 50)"},
    "owner_media": {"estado": HIPOTESE, "recommended": 3, "measured": {}, "obs": "8 = 100 observado"},
    "total_media": {"estado": HIPOTESE, "recommended": 3, "measured": {}, "obs": "9 = 100 observado"},
    "customer_media": {"estado": MEDIDO, "recommended": 3, "measured": {1: 50, 2: 66},
                       "obs": "0 = 0, 1 = 50, 2 = 66, 3 ou mais = 100"},
    "reviews_count": {"estado": HIPOTESE, "recommended": 3, "measured": {}, "obs": "21 = 100 observado"},

    # ---- avaliacoes ----
    "reviews_average": {
        "estado": HIPOTESE,
        # (media de estrelas, nota). 5,0 avaliada como boa no original; o resto e hipotese.
        "good_from": 4.5, "knots": [(0.0, 0), (3.0, 25), (4.0, 75), (4.5, 100)],
        "no_reviews_score": 0,
    },
    "reviews_unanswered": {
        "estado": HIPOTESE,
        # Pela QUANTIDADE de avaliacoes sem resposta: 0 = 100, 1 = 66, 2 = 33, 3 ou mais = 0.
        # So ha ponto medido com 0, 1, 4 e 8 sem resposta (abaixo); 2 e 3 sao interpolacao nossa.
        # A regra por percentual NAO foi descartada: 1 de 25 (4%) deu 66 e 4 de 34 (12%) deu 0, o que tambem
        # cabe numa regra por percentual; so ha 3 locais com avaliacao sem resposta.
        "by_count": {0: 100, 1: 66, 2: 33},
        "zero_from": 3,  # documentacao: de 3 em diante a nota e 0 (by_count.get(n, 0))
        # (sem resposta, total de avaliacoes) -> nota do original. Completa de 08/10/2026.
        "observed": [{"unanswered": 0, "total": 112, "score": 100}, {"unanswered": 1, "total": 25, "score": 66},
                     {"unanswered": 4, "total": 34, "score": 0}, {"unanswered": 8, "total": 25, "score": 0}],
        "obs": "so ha ponto medido com 0, 1, 4 e 8 sem resposta; a regra por percentual NAO foi descartada. "
               "A idade da avaliacao nao parece contar: 8 sem resposta com 0 a 3 dias deram 0.",
        "no_reviews_score": 100,  # nada a responder
    },
    "reviews_no_comment": {
        "estado": HIPOTESE,
        # Pontos medidos (% sem comentario -> nota): 27,3% = 100, 35,7% = 100 e 38,6% = 100 na Completa;
        # 44% = 50 na Pre Analise. O limite do "bom" fica entre 38,6% e 44%; 40% sem comentario
        # (60% com comentario) e hipotese. A curva interpola: good_max_pct -> 100, 44% -> 50, zero_at_pct -> 0.
        "good_max_pct": 40,    # (hipotese) maior que 38,6 (ainda "bom") e menor que 44
        "measured": {44: 50},  # {% sem comentario: nota} usado na curva; origem: Pre Analise
        "observed_good": [27.3, 35.7, 38.6],  # so documentacao: pontos que deram 100 na Completa
        "zero_at_pct": 100,    # (hipotese) a nota chega a 0 em 100% sem comentario
        "no_reviews_score": 0,
    },
    "reviews_trend": {
        "estado": HIPOTESE,
        "recent_days": 90,        # janela das avaliacoes "recentes"; o resto e historico
        "stable_delta": 0.2,      # variacao de media menor que isso = estavel
        "scores": {"up": 100, "stable": 100, "down": 50},
        "insufficient_data": "stable",
    },

    # ---- texto e datas ----
    "business_name": {"estado": HIPOTESE, "max_chars": 98, "obs": "34 = 100; acima do limite = 0"},
    # Itens 29 e 30: curvas em degraus, TODAS hipotese, montadas a partir dos pontos medidos da Completa
    # (10 locais, analises de 08/10/2026). `steps` = [(ate N dias, nota)]; depois do ultimo degrau vale `beyond`.
    # `observed` e so documentacao (dias -> nota do original); o codigo nao le esse campo.
    "last_post": {
        "estado": HIPOTESE,
        "steps": [(30, 100)], "beyond": 0, "no_data_score": 0,
        "observed": [{"days": d, "score": 100} for d in (1, 2, 3, 5, 10)]
                    + [{"days": 38, "score": 0}, {"days": 43, "score": 0}],
        "obs": "100 ate 30 dias e 0 acima: medido 10 dias = 100 e 38 e 43 dias = 0; o corte fica entre 11 e 37 dias "
               "(30 vem do minimo recomendado na Pre Analise). Nao ha ponto medido entre 11 e 37 dias.",
    },
    "last_owner_media": {
        "estado": HIPOTESE,
        "steps": [(59, 100), (119, 50)], "beyond": 0, "no_data_score": 0,
        "ignore_before_year": 1971,  # a API devolve 1970-01-01 para a midia de perfil
        "observed": [{"days": d, "score": 100} for d in (8, 23, 28, 57)] + [{"days": 86, "score": 50}]
                    + [{"days": 152, "score": 0, "obs": "153 na coleta de 09/10; 152 na hora da analise"}],
        "obs": "100 ate 59 dias, 50 de 60 a 119, 0 de 120 em diante. Medido: 57 dias = 100, 86 = 50, 152 = 0 "
               "(a Pre Analise mediu 60 dias = 50). O 100 vai ate algum ponto entre 57 e 85 dias (59 e hipotese); "
               "o 0 comeca em algum ponto desconhecido entre 87 e 151 dias (120 e hipotese).",
        "zero_starts_between_days": (87, 151),
    },
}
