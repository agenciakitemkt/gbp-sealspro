"""Parametros da Analise de Ranking (CLAUDE.md, secao 16). Cada analise guarda os valores com que foi feita."""

# Sobe quando a leitura de um ponto ou o calculo das metricas mudar (as analises guardadas mantem a versao delas).
RANKING_VERSION = "1"

# Grade: lados aceitos (como o GBP Check, de 3x3 a 15x15) e raio, a distancia do centro ate a borda, em metros (o GBP
# Check vai de 100 m a 10 km). Ate 9x9 no inicio; 11x11 a 15x15 liberadas em 2026-10-11, depois de cerca de 1.000
# buscas no dia sem bloqueio. Se o Google pedir verificacao (captcha), a extensao para a coleta e avisa.
GRID_SIZES = (3, 5, 7, 9, 11, 13, 15)
SECONDS_PER_POINT = 1.9  # media medida (pedido + pausa de 1,2 a 2 s), para o tempo estimado no formulario
DEFAULT_GRID = 5
RADIUS_MIN_M, RADIUS_MAX_M = 500, 10000
RADIUS_OPTIONS_M = (500, 1000, 1500, 2000, 3000, 5000)
DEFAULT_RADIUS_M = 2000

# Zoom do mapa em cada ponto: distancia de visao (!1d do parametro pb da busca, em metros). Muda muito o resultado.
# Comparacao com o GBP Check em 8 casos (2026-10-11, CLAUDE.md 16.7): nenhum valor fixo reproduz o original em todos.
# Em segmentos com muitos concorrentes perto (oftalmologista, salao, dentista no centro de BH) bate com 0,5 a 2 km;
# psiquiatra em BH, com 4 km; urologista em cidade vizinha (poucos por perto), so com 16 km. Por isso e uma opcao da analise.
VIEW_OPTIONS_M = {1000: "Bairro (1 km)", 4000: "Região (4 km)", 16000: "Cidade (16 km)"}
VIEW_DISTANCE_M = 1000  # padrao

# Metricas (como o GBP Check, conferidas na referencia de 2026-10-11): posicao "fora dos 20" conta como 21 no ATRP;
# SoLV = % dos pontos no top 3.
RESULTS_PER_POINT = 20
NOT_FOUND_RANK = 21
TOP_N = 3

KEYWORD_MAX = 80
# Varias palavras-chave de uma vez (separadas por virgula, ponto e virgula ou linha), como no GBP Check: uma analise
# por palavra, todas no mesmo lote, rodadas em sequencia pela extensao com um clique.
BATCH_MAX = 5
# Analise criada no app e ainda nao iniciada no Maps: vale por este tempo (depois, crie outra).
PENDING_TTL_MIN = 120

# Lembrete (fase R6, decisao do usuario em 2026-10-11): sem agendamento automatico (a extensao so age com clique);
# o app lista as series cuja ultima analise pronta passou deste prazo, para repetir com um clique.
REMINDER_DAYS = 30

# Mensagem da extensao quando o Google pede verificacao (captcha): num lote, as palavras que faltam nao rodam.
BLOCKED_PREFIX = "o Google pediu uma verificação"
