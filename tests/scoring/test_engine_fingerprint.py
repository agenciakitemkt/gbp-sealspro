"""Trava: o codigo de scoring/ nao pode mudar sem ENGINE_VERSION subir (ou a impressao ser registrada de proposito)."""

import json
import os
import tempfile
import unittest

import ast

from scoring import version
from scoring.pre import version as pre_version
from tests import code_fingerprint as fp


class RegistroDoMotorTest(unittest.TestCase):
    def test_codigo_e_versao_conferem_com_o_registro(self):
        message = fp.explain(fp.load_record(), version.ENGINE_VERSION, fp.file_hashes())
        self.assertIsNone(message, "\n\n" + str(message))

    def test_registro_tem_a_versao_e_todos_os_arquivos(self):
        record = fp.load_record()
        self.assertEqual(record["engine_version"], version.ENGINE_VERSION)
        self.assertEqual(sorted(record["files"]), fp.source_files())

    def test_cobre_os_itens_o_motor_as_curvas_e_a_base(self):
        files = fp.source_files()
        for needed in ("engine.py", "curves.py", "base.py", "items/__init__.py", "items/reviews_unanswered.py",
                       "items/last_owner_media.py", "items/services.py"):
            self.assertIn(needed, files)
        self.assertEqual(sum(1 for f in files if f.startswith("items/") and f != "items/__init__.py"), 21)

    def test_config_e_version_ficam_de_fora(self):  # o config tem hash proprio; version.py guarda a propria versao
        files = fp.source_files()
        self.assertNotIn("config.py", files)
        self.assertNotIn("version.py", files)

    def test_pasta_da_pre_fica_de_fora(self):
        self.assertEqual([f for f in fp.source_files() if f.startswith("pre/")], [])


class RegistroDaPreTest(unittest.TestCase):
    """Mesma trava para o motor da Pre Analise, com PRE_ENGINE_VERSION e registro proprio."""

    def test_codigo_e_versao_conferem_com_o_registro(self):
        message = fp.check(fp.PRE)
        self.assertIsNone(message, "\n\n" + str(message))

    def test_registro_tem_a_versao_e_todos_os_arquivos(self):
        record = fp.load_record(fp.PRE.record)
        self.assertEqual(record["engine_version"], pre_version.PRE_ENGINE_VERSION)
        self.assertEqual(sorted(record["files"]), fp.source_files(fp.PRE))

    def test_cobre_os_20_itens_o_motor_e_os_compartilhados(self):
        files = fp.source_files(fp.PRE)
        for needed in ("base.py", "curves.py", "pre/engine.py", "pre/base.py", "pre/items/__init__.py"):
            self.assertIn(needed, files)
        self.assertEqual(sum(1 for f in files if f.startswith("pre/items/") and f != "pre/items/__init__.py"), 20)
        self.assertNotIn("pre/config.py", files)
        self.assertNotIn("pre/version.py", files)
        self.assertFalse([f for f in files if f.startswith("items/")])  # itens da Completa ficam de fora

    def test_base_entra_nas_duas_impressoes(self):
        for shared in fp.SHARED:
            self.assertIn(shared, fp.source_files(fp.COMPLETA))
            self.assertIn(shared, fp.source_files(fp.PRE))

    def test_lista_de_compartilhados_cobre_tudo_que_a_pre_importa(self):
        """Todo modulo de scoring/ (fora da pre e dos configs) que a Pre importa precisa estar em SHARED."""
        imported = set()
        for rel in fp.source_files(fp.PRE):
            if not rel.startswith("pre/"):
                continue
            with open(os.path.join(fp.SCORING, rel), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("scoring"):
                    imported.add(node.module)
        outside = {m for m in imported if not m.startswith("scoring.pre")} - {"scoring", "scoring.config"}
        self.assertEqual({m.split(".", 1)[1] + ".py" for m in outside} - set(fp.SHARED), set())

    def test_mensagem_fala_da_versao_da_pre(self):
        record = {"engine_version": "1", "fingerprint": fp.fingerprint({"pre/a.py": "h1"}), "files": {"pre/a.py": "h1"}}
        msg = fp.explain(record, "1", {"pre/a.py": "OUTRO"}, fp.PRE)
        self.assertIn("PRE_ENGINE_VERSION continua", msg)
        self.assertIn("scoring/pre/version.py", msg)

    def test_mudanca_em_compartilhado_avisa_dos_dois_motores(self):
        record = {"engine_version": "1", "fingerprint": fp.fingerprint({"base.py": "h1"}), "files": {"base.py": "h1"}}
        for engine in fp.ENGINES:
            msg = fp.explain(record, "1", {"base.py": "OUTRO"}, engine)
            self.assertIn("compartilhado pelos dois motores", msg)


BASE = '''
"""Docstring do modulo."""
from scoring import config


def evaluate(profile, now):
    """Avalia o item."""
    n = len(profile["videos"])  # comentario
    score = 100 if n >= 3 else 50
    return score, "O perfil tem {current} videos.", {"current": n}


ITEM = Item("videos", 5, "Midia: videos", evaluate)
'''


def canon(source):
    return fp.canonical(source)


class CanonicalizacaoTest(unittest.TestCase):
    """O que muda a impressao (logica) e o que nao muda (cosmetico e texto)."""

    def assertSame(self, changed):
        self.assertEqual(canon(BASE), canon(changed))

    def assertDifferent(self, changed):
        self.assertNotEqual(canon(BASE), canon(changed))

    # ---- nao muda ----
    def test_comentario(self):
        self.assertSame(BASE.replace("# comentario", "# outro comentario, bem mais longo").replace("n = len", "# nota\n    n = len"))

    def test_docstring(self):
        self.assertSame(BASE.replace('"""Avalia o item."""', '"""Nova explicacao do item."""').replace("Docstring do modulo.", "Outra."))

    def test_remover_docstring(self):
        self.assertSame(BASE.replace('    """Avalia o item."""\n', ""))

    def test_formatacao_e_espacos(self):
        self.assertSame(BASE.replace("score = 100 if n >= 3 else 50", "score = (\n        100\n        if n >= 3\n        else 50\n    )"))

    def test_texto_da_mensagem(self):
        self.assertSame(BASE.replace("O perfil tem {current} videos.", "Foram publicados {current} videos no perfil, otimo."))

    def test_titulo_do_item(self):
        self.assertSame(BASE.replace('"Midia: videos"', '"Videos publicados"'))

    # ---- muda ----
    def test_numero_de_um_limite(self):
        self.assertDifferent(BASE.replace("n >= 3", "n >= 4"))

    def test_nota(self):
        self.assertDifferent(BASE.replace("else 50", "else 66"))

    def test_operador(self):
        self.assertDifferent(BASE.replace("n >= 3", "n > 3"))

    def test_regra_nova(self):
        self.assertDifferent(BASE.replace("score = 100 if", "n = n + 1\n    score = 100 if"))

    def test_dado_que_o_item_le(self):
        self.assertDifferent(BASE.replace('profile["videos"]', 'profile["media"]'))

    def test_id_legado_do_item(self):
        self.assertDifferent(BASE.replace('"videos", 5,', '"videos", 6,'))

    def test_chave_de_uma_palavra(self):
        self.assertDifferent(BASE.replace('{"current": n}', '{"atual": n}'))

    def test_renomear_variavel_conta_como_mudanca_e_exige_registrar(self):
        self.assertDifferent(BASE.replace("n = len", "total = len").replace("n >= 3", "total >= 3").replace('{"current": n}', '{"current": total}'))


class MensagensDeFalhaTest(unittest.TestCase):
    RECORD = {"engine_version": "1", "fingerprint": fp.fingerprint({"a.py": "h1", "items/b.py": "h2"}),
              "files": {"a.py": "h1", "items/b.py": "h2"}}

    def test_tudo_igual_nao_falha(self):
        self.assertIsNone(fp.explain(self.RECORD, "1", {"a.py": "h1", "items/b.py": "h2"}))

    def test_codigo_mudou_sem_subir_a_versao_explica_as_duas_saidas(self):
        msg = fp.explain(self.RECORD, "1", {"a.py": "h1", "items/b.py": "OUTRO"})
        self.assertIn("ENGINE_VERSION continua", msg)
        self.assertIn("items/b.py", msg)
        self.assertNotIn("  - a.py", msg)  # so lista o que mudou
        self.assertIn("1. ", msg)
        self.assertIn("suba ENGINE_VERSION", msg)
        self.assertIn("2. ", msg)
        self.assertIn("cosmetica", msg)
        self.assertEqual(msg.count("-m tests.code_fingerprint --update"), 2)

    def test_versao_subiu_mas_falta_registrar(self):
        msg = fp.explain(self.RECORD, "2", {"a.py": "h1", "items/b.py": "OUTRO"})
        self.assertIn("subiu de \"1\" para \"2\"", msg)
        self.assertIn("--update", msg)

    def test_versao_mudou_sem_mudar_o_codigo(self):
        msg = fp.explain(self.RECORD, "2", {"a.py": "h1", "items/b.py": "h2"})
        self.assertIn("sem mudanca na logica", msg)

    def test_arquivo_removido_e_arquivo_novo_aparecem(self):
        gone = fp.explain(self.RECORD, "1", {"a.py": "h1"})
        self.assertIn("items/b.py (removido)", gone)
        new = fp.explain(self.RECORD, "1", {"a.py": "h1", "items/b.py": "h2", "items/c.py": "h3"})
        self.assertIn("items/c.py", new)


class RegistroEmDiscoTest(unittest.TestCase):
    def test_salvar_e_ler(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.json")
            record = fp.save_record("7", {"x.py": "abc"}, path)
            self.assertEqual(fp.load_record(path), record)
            self.assertEqual(record["engine_version"], "7")
            self.assertEqual(record["fingerprint"], fp.fingerprint({"x.py": "abc"}))

    def test_atualizar_conserta_o_registro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.json")
            fp.save_record("1", {"x.py": "velho"}, path)
            self.assertIsNotNone(fp.explain(fp.load_record(path), "1", {"x.py": "novo"}))
            fp.save_record("1", {"x.py": "novo"}, path)
            self.assertIsNone(fp.explain(fp.load_record(path), "1", {"x.py": "novo"}))

    def test_impressao_nao_depende_da_ordem(self):
        self.assertEqual(fp.fingerprint({"a": "1", "b": "2"}), fp.fingerprint({"b": "2", "a": "1"}))


if __name__ == "__main__":
    unittest.main()
