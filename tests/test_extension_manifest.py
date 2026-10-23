"""Trava das permissoes da extensao (CLAUDE.md, 13.10): so o minimo. Mudar aqui exige revisao de seguranca."""

import json
import os
import unittest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extension")
# Na conferencia manual: se o Maps do usuario abrir em google.com.br, acrescentar so esse dominio aqui e no manifest.
# "maps?*": a aba aberta pelo botao da busca comeca em https://www.google.com/maps?cid=<CID>&hl=pt-BR.
MAPS_MATCHES = ["https://www.google.com/maps/*", "https://www.google.com/maps?*"]
SEARCH_MATCHES = ["https://www.google.com/search*", "https://www.google.com.br/search*"]


def manifest():
    with open(os.path.join(ROOT, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


class ManifestTest(unittest.TestCase):
    def test_permissoes_minimas(self):
        m = manifest()
        self.assertEqual(m["manifest_version"], 3)
        self.assertEqual(m["permissions"], ["storage"])
        self.assertEqual(m["host_permissions"], ["http://127.0.0.1:8000/*"])
        self.assertNotIn("optional_permissions", m)
        self.assertNotIn("optional_host_permissions", m)

    def test_sem_portas_abertas_para_sites(self):
        m = manifest()
        for key in ("web_accessible_resources", "content_security_policy", "key",
                    "update_url", "commands", "declarative_net_request"):
            self.assertNotIn(key, m)

    def test_so_o_app_local_fala_com_a_extensao(self):
        """Clique unico da Analise de Ranking (CLAUDE.md, 16.3, decisao do usuario em 2026-10-11): so paginas do app local
        podem mandar mensagem para a extensao, e so o numero da analise (o resto vem do app com o segredo).
        SE O APP FOR PARA A INTERNET: trocar este endereco pelo dominio do app (so ele, com https) aqui, no manifest e
        em APP de src/lib/run.js. Nunca usar curinga de dominio nem acrescentar sites de terceiros."""
        self.assertEqual(manifest().get("externally_connectable"), {"matches": ["http://127.0.0.1:8000/*"]})

    def test_content_scripts_so_no_maps_e_na_busca(self):
        scripts = manifest()["content_scripts"]
        self.assertEqual(len(scripts), 3)
        for cs in scripts:
            self.assertNotIn("all_frames", cs)
            self.assertNotIn("exclude_matches", cs)
            self.assertNotIn("match_about_blank", cs)
        main, isolated, search = scripts
        self.assertEqual(main["matches"], MAPS_MATCHES)
        self.assertEqual(isolated["matches"], MAPS_MATCHES)
        self.assertEqual(search["matches"], SEARCH_MATCHES)
        self.assertEqual(main["world"], "MAIN")
        self.assertNotIn("world", isolated)  # ISOLATED (padrao)
        self.assertNotIn("world", search)
        all_js = main["js"] + isolated["js"] + search["js"]
        self.assertNotIn("src/lib/run.js", all_js)  # envio e segredo: so no service worker
        # o Chrome injeta um mesmo arquivo uma vez so por pagina: as duas entradas do Maps nao podem dividir arquivos
        self.assertEqual(set(main["js"]) & set(isolated["js"]), set())
        # na busca so o botao e a leitura do CID: nada de hook de rede
        self.assertEqual(search["js"], ["src/lib/cid.js", "src/lib/button.js", "src/lib/reviews-search.js", "src/search.js"])

    def test_service_worker_e_opcoes(self):
        m = manifest()
        self.assertEqual(m["background"], {"service_worker": "src/background.js"})
        self.assertEqual(m["options_page"], "options.html")
        for f in ["src/background.js", "options.html", "src/options.js"] + \
                [j for cs in m["content_scripts"] for j in cs["js"]]:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, f)), f)


if __name__ == "__main__":
    unittest.main()
