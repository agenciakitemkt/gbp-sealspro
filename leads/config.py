"""Parametros da Busca de Leads (CLAUDE.md, secao 18). Cada busca guarda os valores com que foi feita."""

# Sobe quando a leitura dos resultados ou o calculo da qualidade mudar (as buscas guardadas mantem a versao delas).
LEADS_VERSION = "1"

KEYWORD_MAX = 80
REGION_MAX = 120

# Abrangencia: a grade de pontos espalhada sobre a regiao (o retangulo que o OpenStreetMap devolve para ela) e quantas
# paginas de 20 resultados ler em cada ponto. Teste de 2026-10-14 ("agencia de marketing", Belo Horizonte): 9 pontos
# com 1 pagina = 115 a 131 leads distintos; 1 ponto com 4 paginas = 80, sem repetir. Quando uma pagina vem com menos
# de 20, as seguintes daquele ponto nao sao pedidas.
SCOPES = {
    "rapida": {"label": "Rápida", "grid": 3, "pages": 2},
    "normal": {"label": "Normal", "grid": 3, "pages": 3},
    "ampla": {"label": "Ampla", "grid": 5, "pages": 3},
    "muito_ampla": {"label": "Muito ampla", "grid": 7, "pages": 3},
}
DEFAULT_SCOPE = "normal"
RESULTS_PER_PAGE = 20
SECONDS_PER_REQUEST = 1.9  # o mesmo ritmo do Ranking (pedido + pausa de 1,2 a 2 s)

# Regiao: metade do lado minimo do retangulo (um bairro pequeno vira pelo menos 2 km x 2 km) e maximo (uma regiao
# maior que isso, como um estado, e recusada: a grade ficaria rala demais).
REGION_MIN_HALF_M = 1000
REGION_MAX_SIDE_M = 80000
# Margem para "dentro da regiao": a busca num ponto da borda traz negocios um pouco fora do retangulo.
REGION_MARGIN_M = 500

# Zoom de cada ponto (distancia de visao, !1d do parametro pb): proporcional ao espaco entre os pontos, entre estes
# limites (hipotese; no teste, 4 e 8 km deram quase o mesmo numero de leads em BH).
VIEW_MIN_M, VIEW_MAX_M = 2000, 16000

# Busca criada no app e ainda nao iniciada no Maps: vale por este tempo (depois, crie outra).
PENDING_TTL_MIN = 120

# Mensagem da extensao quando o Google pede verificacao (captcha), a mesma do Ranking.
BLOCKED_PREFIX = "o Google pediu uma verificação"
