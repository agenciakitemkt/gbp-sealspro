"""Versao do motor e do config, guardadas com cada analise para que mudancas futuras nas curvas nao distorcam
a comparacao historica.

ENGINE_VERSION sobe a mao sempre que a LOGICA do motor mudar (formula da nota geral, regra de um item, status...).
Mudancas so de numeros no scoring/config.py nao precisam de bump: o hash do config muda sozinho.
"""

import hashlib
import json

from scoring import config

ENGINE_VERSION = "1"


def config_snapshot():
    """Tudo o que influencia a nota e vem de scoring/config.py."""
    return {"CONFIG": config.CONFIG, "OVERALL": config.OVERALL, "OVERALL_BANDS": config.OVERALL_BANDS,
            "BAD_BELOW": config.BAD_BELOW, "GOOD_AT": config.GOOD_AT,
            "BINARY_FAIL_SCORE": config.BINARY_FAIL_SCORE}


def config_json():
    return json.dumps(config_snapshot(), sort_keys=True, ensure_ascii=False, default=list)


def config_hash():
    return hashlib.sha256(config_json().encode("utf-8")).hexdigest()
