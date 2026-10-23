"""Versao do motor e do config da Pre Analise, no mesmo padrao da Completa (scoring/version.py).

PRE_ENGINE_VERSION sobe a mao sempre que a LOGICA do motor da Pre mudar, inclusive em scoring/base.py e
scoring/curves.py, que os dois motores compartilham. A trava de impressao digital (tests/code_fingerprint.py) confere.
"""

import hashlib
import json

from scoring import config as shared
from scoring.pre import config

PRE_ENGINE_VERSION = "12"  # 2: notCollected e warnings; 3: N da tendencia no motor; 4: leitor da extensao passa a avaliar a ultima postagem (fonte A) e a recusar a fonte A de outro local; 5: redes sociais do bloco "Perfis" da busca do Google; 6: fotos 360 pela categoria da galeria; 7: amostra de avaliacoes nas 100 mais recentes; 8: amostra de menor nota do Maps; 9: amostra da caixa de avaliacoes da busca, igual a do GBP Check; 10: perfis com ate 130 avaliacoes usam todas; 11: dias na escala do GBP Check (texto do Google); 12: concorrentes de categoria parecida


def config_snapshot():
    """Tudo o que influencia a nota da Pre: o config proprio e os valores compartilhados com a Completa."""
    return {"CONFIG": config.CONFIG, "OVERALL": shared.OVERALL, "OVERALL_BANDS": shared.OVERALL_BANDS,
            "BAD_BELOW": shared.BAD_BELOW, "GOOD_AT": shared.GOOD_AT}


def config_json():
    return json.dumps(config_snapshot(), sort_keys=True, ensure_ascii=False, default=list)


def config_hash():
    return hashlib.sha256(config_json().encode("utf-8")).hexdigest()
