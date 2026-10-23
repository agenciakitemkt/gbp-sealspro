"""Suite de testes. Duas protecoes contra tocar nos dados reais do projeto (data/):

1. Prevencao: ao importar o pacote, `storage` passa a apontar para uma pasta temporaria. Qualquer teste que use o
   armazenamento sem isolar por conta propria escreve la, nunca em data/. (Foi assim que arquivos falsos chegaram a
   data/raw: o caminho do bruto era fixo na importacao.)
2. Deteccao: guarda-se aqui a impressao digital de data/ e o teste `test_zz_dados_reais_intactos` (o ultimo a rodar)
   falha se qualquer arquivo mudou durante a execucao.
"""

import os
import tempfile

import storage
from tests import guard

# Impressao de data/ ANTES de qualquer teste. data/prints so tem capturas de tela tiradas a mao.
REAL_DATA_AT_START = guard.snapshot(guard.REAL_DATA, exclude=("prints",))

_SANDBOX = tempfile.TemporaryDirectory(prefix="gbp-testes-")
storage.DATA = _SANDBOX.name
storage.DB = os.path.join(_SANDBOX.name, "gbp.db")
