"""Impressao digital da LOGICA dos motores de nota (scoring/), para exigir que a versao do motor suba quando ela muda.

Ha dois motores, cada um com a propria versao e o proprio registro:
- Completa: ENGINE_VERSION (scoring/version.py), registro em tests/scoring/engine_fingerprint.json. Entra todo o
  scoring/, menos a pasta scoring/pre/.
- Pre Analise: PRE_ENGINE_VERSION (scoring/pre/version.py), registro em tests/scoring/pre_engine_fingerprint.json.
  Entra scoring/pre/ e os arquivos compartilhados (SHARED: base.py e curves.py).
Os compartilhados entram nas DUAS impressoes: mudar a logica de base.py ou curves.py exige decidir as duas versoes.

O que entra: o codigo, em forma canonica obtida da arvore sintatica.
O que NAO entra, de proposito:
- comentarios, docstrings, formatacao e quebras de linha;
- textos de mensagem e titulos: qualquer string com espaco e letras (ex.: "O perfil tem logotipo.") vira um marcador;
- config.py (os numeros ja tem o proprio hash do config, ver version.py) e version.py de cada motor.
Limites conhecidos: uma string de uma palavra so (ex.: o titulo "Website") conta como logica; mudancas fora de
scoring/ (como collector/normalize.py ou collector_pre/from_original.py) nao sao cobertas.

Atualizar os registros (depois de subir a versao, ou numa mudanca so cosmetica):
    ./.venv/bin/python -m tests.code_fingerprint --update
"""

import ast
import hashlib
import importlib
import json
import os
import re
import sys
from dataclasses import dataclass

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORING = os.path.join(PROJECT, "scoring")
RECORDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scoring")
SHARED = ("base.py", "curves.py")              # arquivos de scoring/ usados pelos dois motores
_SKIP_FIELDS = {"ctx", "type_comment", "kind", "type_params"}  # campos que mudam entre versoes do Python sem mudar a logica
MESSAGE = "<texto>"
UPDATE = "./.venv/bin/python -m tests.code_fingerprint --update"


@dataclass(frozen=True)
class Engine:
    key: str
    label: str
    version_var: str        # nome da constante da versao
    version_module: str     # modulo que a define
    record: str             # arquivo do registro
    folder: str             # pasta do motor, relativa a scoring/ ("" = raiz)
    skip_folders: tuple     # subpastas que pertencem a outro motor
    shared: tuple           # arquivos de fora da pasta que tambem entram

    @property
    def version_file(self):
        return self.version_module.replace(".", "/") + ".py"


COMPLETA = Engine("completa", "Analise Completa", "ENGINE_VERSION", "scoring.version",
                  os.path.join(RECORDS, "engine_fingerprint.json"), "", ("pre",), ())
PRE = Engine("pre", "Pre Analise", "PRE_ENGINE_VERSION", "scoring.pre.version",
             os.path.join(RECORDS, "pre_engine_fingerprint.json"), "pre", (), SHARED)
ENGINES = (COMPLETA, PRE)
RECORD = COMPLETA.record


def _is_message(value):
    return bool(re.search(r"\s", value) and re.search(r"[^\W\d_]", value))


class _DropDocstrings(ast.NodeTransformer):
    """Remove strings soltas usadas como comentario (docstrings incluidas)."""

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)


def _canon(node):
    if isinstance(node, ast.AST):
        parts = ",".join(_canon(getattr(node, f, None)) for f in node._fields if f not in _SKIP_FIELDS)
        return f"{type(node).__name__}({parts})"
    if isinstance(node, list):
        return "[" + ",".join(_canon(x) for x in node) + "]"
    if isinstance(node, str):
        return MESSAGE if _is_message(node) else repr(node)
    return repr(node)


def canonical(source):
    """Forma canonica de um arquivo: a mesma para codigo que so difere em comentario, docstring, formatacao ou texto de mensagem."""
    tree = _DropDocstrings().visit(ast.parse(source))
    return _canon(tree)


def source_files(engine=COMPLETA):
    """Caminhos relativos a scoring/ (com '/') dos arquivos que entram na impressao do motor, em ordem."""
    base = os.path.join(SCORING, engine.folder)
    excluded = {f"{engine.folder}/{n}".lstrip("/") for n in ("config.py", "version.py")}
    out = list(engine.shared)
    for folder, dirs, files in os.walk(base):
        top = folder == base
        dirs[:] = sorted(d for d in dirs if d != "__pycache__" and not (top and d in engine.skip_folders))
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(folder, name), SCORING).replace(os.sep, "/")
            if rel not in excluded and rel not in out:
                out.append(rel)
    return sorted(out)


def file_hashes(engine=COMPLETA):
    hashes = {}
    for rel in source_files(engine):
        with open(os.path.join(SCORING, rel), encoding="utf-8") as f:
            hashes[rel] = hashlib.sha256(canonical(f.read()).encode("utf-8")).hexdigest()
    return hashes


def fingerprint(hashes):
    return hashlib.sha256("\n".join(f"{p} {h}" for p, h in sorted(hashes.items())).encode("utf-8")).hexdigest()


def current_engine_version(engine=COMPLETA):
    sys.path.insert(0, PROJECT)
    return getattr(importlib.import_module(engine.version_module), engine.version_var)


def load_record(path=RECORD):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_record(engine_version, hashes, path=RECORD):
    record = {"engine_version": engine_version, "fingerprint": fingerprint(hashes), "files": dict(sorted(hashes.items()))}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return record


def explain(record, engine_version, hashes, engine=COMPLETA):
    """None se o registro confere com o codigo e a versao atuais; senao, a mensagem que diz o que fazer."""
    code_changed = fingerprint(hashes) != record["fingerprint"]
    version_changed = engine_version != record["engine_version"]
    if not code_changed and not version_changed:
        return None
    var, where = engine.version_var, engine.version_file
    changed = sorted(p for p in hashes if record["files"].get(p) != hashes[p]) + \
        sorted(f"{p} (removido)" for p in record["files"] if p not in hashes)
    files = "\n  - ".join(changed) if changed else "(nenhum arquivo)"
    shared = [p for p in changed if p in SHARED]
    shared_note = (f"\n{', '.join(shared)} e compartilhado pelos dois motores (Completa e Pre Analise): "
                   "decida a versao de cada um.\n" if shared else "")
    if code_changed and not version_changed:
        return (
            f"[{engine.label}] A logica do motor mudou, mas {var} continua \"{engine_version}\".\n"
            f"Arquivos com mudanca de logica:\n  - {files}\n{shared_note}\n"
            "Escolha UMA das saidas:\n"
            "  1. A mudanca altera a nota que um perfil recebe (regra de item, formula, status, item novo/removido): "
            f"suba {var} em {where} e depois registre a nova impressao com\n"
            f"       {UPDATE}\n"
            "  2. A mudanca e so cosmetica (renomear variavel, reorganizar codigo, sem efeito na nota): "
            "NAO suba a versao; apenas registre a nova impressao com\n"
            f"       {UPDATE}\n"
            "Comentarios, docstrings, formatacao e textos de mensagem nao entram na impressao.\n"
            "Ver 'Versao do motor e do config' no CLAUDE.md.")
    if code_changed and version_changed:
        return (
            f"[{engine.label}] {var} subiu de \"{record['engine_version']}\" para \"{engine_version}\", mas a impressao "
            "registrada ainda e a anterior.\nArquivos com mudanca de logica:\n  - " + files + "\n" + shared_note + "\n"
            f"Falta registrar a nova impressao: {UPDATE}")
    return (
        f"[{engine.label}] {var} mudou de \"{record['engine_version']}\" para \"{engine_version}\" sem mudanca na logica "
        f"do motor.\nSe a subida foi intencional, registre: {UPDATE}\n"
        f"Se nao, volte {var} para o valor anterior.")


def check(engine):
    """Como `explain`, para o motor `engine` no estado atual do disco (tambem avisa se o registro nao existe)."""
    if not os.path.exists(engine.record):
        return f"[{engine.label}] Sem registro em {os.path.relpath(engine.record, PROJECT)}. Registre com: {UPDATE}"
    return explain(load_record(engine.record), current_engine_version(engine), file_hashes(engine), engine)


def main(argv):
    if argv[1:] == ["--update"]:
        for engine in ENGINES:
            hashes = file_hashes(engine)
            before = load_record(engine.record) if os.path.exists(engine.record) else None
            changed = before is None or before["fingerprint"] != fingerprint(hashes)
            record = save_record(current_engine_version(engine), hashes, engine.record)
            bumped = before is not None and before["engine_version"] != record["engine_version"]
            note = ("registro novo" if before is None else
                    "codigo mudou, versao subiu" if changed and bumped else
                    "codigo mudou, versao mantida (mudanca cosmetica)" if changed else
                    "sem mudanca no codigo")
            print(f"{engine.label}: {engine.version_var} {record['engine_version']}, impressao "
                  f"{record['fingerprint'][:12]}…, {len(record['files'])} arquivos "
                  f"({os.path.relpath(engine.record, PROJECT)}): {note}")
        return 0
    messages = [m for m in (check(e) for e in ENGINES) if m]
    print("\n\n".join(messages) or "Registros conferem com o codigo e as versoes atuais.")
    return 1 if messages else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
