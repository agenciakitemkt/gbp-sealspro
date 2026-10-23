"""Protecao dos dados reais (data/): impressao digital de uma pasta e comparacao entre duas impressoes."""

import hashlib
import os

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA = os.path.join(PROJECT, "data")


def snapshot(root, exclude=()):
    """{caminho relativo: sha256} de todos os arquivos sob `root` ({} se a pasta nao existir).

    `exclude` = nomes de subpastas de primeiro nivel a ignorar.
    """
    out = {}
    if not os.path.isdir(root):
        return out
    for folder, dirs, files in os.walk(root):
        if folder == root:
            dirs[:] = [d for d in dirs if d not in exclude]
        for name in files:
            path = os.path.join(folder, name)
            with open(path, "rb") as f:
                out[os.path.relpath(path, root)] = hashlib.sha256(f.read()).hexdigest()
    return out


def diff(before, after):
    """Lista legivel do que mudou entre duas impressoes."""
    changes = [f"removido: {p}" for p in sorted(before.keys() - after.keys())]
    changes += [f"novo: {p}" for p in sorted(after.keys() - before.keys())]
    changes += [f"alterado: {p}" for p in sorted(p for p in before.keys() & after.keys() if before[p] != after[p])]
    return changes
