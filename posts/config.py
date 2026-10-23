"""Limites e regras do agendamento de postagens (CLAUDE.md, secao 17)."""

SUMMARY_MAX = 1500  # limite do Google para o texto da postagem
URL_MAX = 2000

# Botoes da postagem (actionType da API). CALL nao leva link: o Google usa o telefone do perfil.
CTA_LABELS = {
    "": "Nenhum",
    "LEARN_MORE": "Saiba mais",
    "BOOK": "Reservar",
    "ORDER": "Pedir on-line",
    "SHOP": "Comprar",
    "SIGN_UP": "Inscrever-se",
    "CALL": "Ligar agora",
}
CTA_WITHOUT_URL = {"", "CALL"}

# Imagem: o app aceita JPG, PNG e WebP e grava sempre JPEG (o Google aceita JPG e PNG nas postagens).
IMAGE_UPLOAD_MAX = 15 * 1024 * 1024   # tamanho do arquivo enviado pela tela
IMAGE_MIN_SIDE = 250                  # minimo do Google para fotos
IMAGE_MAX_SIDE = 1600                 # lado maior depois de reduzir (a postagem aparece pequena)
IMAGE_MIN_BYTES = 10 * 1024           # minimo do Google para fotos
IMAGE_MAX_BYTES = 5 * 1024 * 1024     # maximo do Google para fotos
IMAGE_MAX_PIXELS = 60_000_000         # contra imagem "bomba" (descompacta para um tamanho enorme)
ORPHAN_IMAGE_HOURS = 24               # imagem enviada e nunca usada numa postagem: apagada depois disso

# Publicador
MAX_ATTEMPTS = 5                          # tentativas com erro passageiro antes de "Falhou"
RETRY_MINUTES = [2, 5, 15, 30, 60]        # espera antes da tentativa seguinte (indice = tentativas ja feitas - 1)
LATE_HOLD_HOURS = 24                      # agendada vencida ha mais que isso e nunca tentada: espera o usuario decidir
STUCK_MINUTES = 15                        # "publicando" por mais que isso = o processo caiu no meio
LATE_NOTICE_MINUTES = 15                  # publicada mais de 15 min depois do horario: mostra o atraso
MEDIA_WAIT_TRIES = 10                     # leituras da foto ate o link definitivo aparecer
MEDIA_WAIT_SECONDS = 3
REFRESH_DAYS = 3                          # releitura do estado no Google (processando -> no ar ou recusada)
DUPLICATE_WINDOW_MINUTES = 10             # postagem igual criada ate 10 min antes da 1a tentativa = a mesma

# Agendador do macOS (launchd)
LAUNCHD_LABEL = "com.sealspro.gbp-publicador"
LAUNCHD_INTERVAL_SECONDS = 300
STALE_PUBLISHER_MINUTES = 30  # a tela avisa se o publicador nao roda ha mais que isso

DEFAULT_HOUR = "09:00"  # horario sugerido ao clicar num dia do calendario
