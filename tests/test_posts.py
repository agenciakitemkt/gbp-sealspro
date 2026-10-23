"""Agendamento de postagens (CLAUDE.md, secao 17): imagem, formulario, publicador, telas e as travas de seguranca.
Nada aqui fala com o Google: o cliente e falso."""

import io
import os
import re
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from PIL import Image
from starlette.testclient import TestClient

import storage
from posts import config, form as post_form, images, launchd, publisher, view
from posts.google_api import GoogleError, TokenError, definitive_url
from tests.test_history import TempStorage
from web import app as webapp
from web import postagens as postagens_web

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc)
ORIGIN = {"origin": "http://127.0.0.1:8000"}


def photo(w=1200, h=900, fmt="JPEG", mode="RGB", exif=None):
    # ruido: uma imagem lisa vira um JPEG pequeno demais (o Google exige 10 KB)
    if mode == "P":
        img = Image.new("P", (w, h))
    else:
        img = Image.frombytes(mode, (w, h), os.urandom(w * h * len(mode)))
    buf = io.BytesIO()
    kw = {"exif": exif} if exif is not None else {}
    img.save(buf, fmt, **kw)
    return buf.getvalue()


class FakeClient:
    """Imita o Google: registra as chamadas e devolve respostas programadas."""

    def __init__(self, media_urls=None, create_errors=None, state="PROCESSING"):
        self.calls = []
        self.media_urls = list(media_urls or ["https://lh3.googleusercontent.com/grass-cs/ok=s0"])
        self.create_errors = list(create_errors or [])
        self.state = state
        self.created = []

    def upload_photo(self, account_id, location_id, jpeg):
        self.calls.append(("upload", account_id, location_id, len(jpeg)))
        return {"name": f"{account_id}/{location_id}/media/M1",
                "googleUrl": "https://lh3.googleusercontent.com/gpu-csl/provisorio"}

    def get_media(self, name):
        self.calls.append(("get_media", name))
        url = self.media_urls.pop(0) if len(self.media_urls) > 1 else self.media_urls[0]
        return {"name": name, "googleUrl": url}

    def create_post(self, account_id, location_id, body):
        self.calls.append(("create", body))
        post = {"name": f"{account_id}/{location_id}/localPosts/{len(self.created) + 1}", "summary": body["summary"],
                "state": self.state, "createTime": NOW.isoformat().replace("+00:00", "Z"),
                "searchUrl": "https://local.google.com/place?id=1&use=posts&lpsid=X"}
        if self.create_errors:
            err = self.create_errors.pop(0)
            if getattr(err, "created_anyway", False):
                self.created.append(post)
            raise err
        self.created.append(post)
        return post

    def get_post(self, name):
        self.calls.append(("get_post", name))
        return {"name": name, "state": self.state}

    def recent_posts(self, account_id, location_id):
        self.calls.append(("recent",))
        return list(self.created)

    def count(self, kind):
        return sum(c[0] == kind for c in self.calls)


class Base(TempStorage):
    def new_post(self, when=NOW, image="", status=None, **kw):
        fields = {"summary": "Novidade do consultório", "cta_type": "LEARN_MORE", "cta_url": "https://exemplo.com",
                  "image": image, "scheduled_at": publisher.iso(when)}
        fields.update(kw)
        pid = storage.create_post(self.db, "locations/1", **fields)
        if status:
            storage.update_post(self.db, pid, status=status)
        return pid

    def post(self, pid):
        return storage.get_post(self.db, pid)


# ---------------------------------------------------------------------------
# Imagem
# ---------------------------------------------------------------------------

class ImagensTest(Base):
    def test_png_transparente_vira_jpeg_sem_transparencia(self):
        jpeg, w, h = images.prepare(photo(800, 600, "PNG", "RGBA"))
        self.assertEqual((w, h), (800, 600))
        with Image.open(io.BytesIO(jpeg)) as img:
            self.assertEqual((img.format, img.mode), ("JPEG", "RGB"))

    def test_metadados_do_celular_nao_vao_para_o_google(self):
        exif = Image.Exif()
        exif[0x010F] = "Fabricante"  # Make
        exif[0x8825] = {2: (19.0, 55.0, 0.0)}  # GPS
        jpeg, _, _ = images.prepare(photo(800, 600, exif=exif.tobytes()))
        with Image.open(io.BytesIO(jpeg)) as img:
            self.assertEqual(dict(img.getexif()), {})

    def test_reduz_imagem_grande(self):
        _, w, h = images.prepare(photo(2400, 1800))
        self.assertEqual((w, h), (1600, 1200))

    def test_recusas_explicadas(self):
        for data, trecho in ((b"", "Nenhum arquivo"), (b"nao sou imagem", "Não foi possível ler"),
                             (photo(200, 600), "pequena demais"), (photo(400, 400, "GIF", "P"), "Formato não aceito")):
            with self.subTest(trecho=trecho):
                with self.assertRaisesRegex(images.ImageError, trecho):
                    images.prepare(data)

    def test_token_nao_deixa_sair_da_pasta(self):
        for token in ("../gbp", "a" * 31, "A" * 32, "../../etc/passwd"):
            with self.assertRaises(images.ImageError):
                images.path_for(token)
        self.assertFalse(images.exists("../gbp"))

    def test_apaga_so_imagens_sem_uso_e_antigas(self):
        usada, solta, nova = (images.save(photo(400, 300))["token"] for _ in range(3))
        velho = time.time() - (config.ORPHAN_IMAGE_HOURS + 1) * 3600
        for t in (usada, solta):
            os.utime(images.path_for(t), (velho, velho))
        self.assertEqual(images.remove_orphans({usada}), [solta])
        self.assertTrue(images.exists(usada) and images.exists(nova))


# ---------------------------------------------------------------------------
# Formulario
# ---------------------------------------------------------------------------

class FormularioTest(Base):
    def form(self, **kw):
        f = {"texto": "Texto", "botao": "LEARN_MORE", "url": "https://exemplo.com", "quando": "agendar",
             "data_hora": "2026-10-20T09:00"}
        f.update(kw)
        return post_form.validate(f, NOW)

    def test_agendamento_em_brasilia_vira_utc(self):
        fields, errors = self.form()
        self.assertEqual(errors, [])
        self.assertEqual(fields["scheduled_at"], "2026-10-20T12:00:00+00:00")

    def test_erros(self):
        casos = [({"texto": "  "}, "Escreva o texto"), ({"texto": "x" * 1501}, "1500 caracteres"),
                 ({"url": ""}, "link do botão"), ({"url": "javascript:alert(1)"}, "https://"),
                 ({"data_hora": "2026-10-13T08:00"}, "já passaram"), ({"data_hora": "amanha"}, "data e a hora"),
                 ({"botao": "HACK"}, "Botão inválido"), ({"imagem": "f" * 32}, "imagem não foi encontrada"),
                 ({"data_hora": "2028-01-01T09:00"}, "dentro de um ano")]
        for extra, trecho in casos:
            with self.subTest(extra=extra):
                _, errors = self.form(**extra)
                self.assertTrue(any(trecho in e for e in errors), errors)

    def test_ligar_e_sem_botao_nao_levam_link(self):
        for botao in ("CALL", ""):
            fields, errors = self.form(botao=botao, url="https://ignorado.com")
            self.assertEqual((errors, fields["cta_url"]), ([], ""))

    def test_publicar_agora_ignora_a_data(self):
        fields, errors = self.form(quando="agora", data_hora="")
        self.assertEqual(errors, [])
        self.assertTrue(fields["now"])
        self.assertEqual(fields["scheduled_at"], publisher.iso(NOW))


# ---------------------------------------------------------------------------
# Publicador
# ---------------------------------------------------------------------------

class PublicadorTest(Base):
    def test_publica_com_imagem_esperando_o_link_definitivo(self):
        token = images.save(photo())["token"]
        pid = self.new_post(image=token)
        fake = FakeClient(media_urls=["https://lh3.googleusercontent.com/gpu-csl/x",
                                      "https://lh3.googleusercontent.com/grass-cs/final=s0"])
        sleeps = []
        self.assertEqual(publisher.publish_one(self.db, pid, fake, NOW, sleeps.append), "publicada")
        body = [c for c in fake.calls if c[0] == "create"][0][1]
        self.assertEqual(body["media"], [{"mediaFormat": "PHOTO",
                                          "sourceUrl": "https://lh3.googleusercontent.com/grass-cs/final=s0"}])
        self.assertEqual(body["callToAction"], {"actionType": "LEARN_MORE", "url": "https://exemplo.com"})
        self.assertEqual((body["topicType"], body["languageCode"]), ("STANDARD", "pt-BR"))
        self.assertEqual(sleeps, [config.MEDIA_WAIT_SECONDS])
        p = self.post(pid)
        self.assertEqual((p["status"], p["google_state"], p["attempts"]), ("publicada", "PROCESSING", 1))
        self.assertTrue(p["search_url"].startswith("https://local.google.com/"))

    def test_sem_imagem_e_ligar_sem_link(self):
        pid = self.new_post(cta_type="CALL", cta_url="")
        fake = FakeClient()
        publisher.publish_one(self.db, pid, fake, NOW)
        body = fake.calls[-1][1]
        self.assertEqual(body["callToAction"], {"actionType": "CALL"})
        self.assertNotIn("media", body)
        self.assertEqual(fake.count("upload"), 0)

    def test_erro_passageiro_agenda_nova_tentativa_e_depois_desiste(self):
        pid = self.new_post()
        fake = FakeClient(create_errors=[GoogleError("500", status=500, retryable=True)] * config.MAX_ATTEMPTS)
        now = NOW
        for i in range(config.MAX_ATTEMPTS):
            result = publisher.publish_one(self.db, pid, fake, now)
            p = self.post(pid)
            if i < config.MAX_ATTEMPTS - 1:
                self.assertEqual((result, p["status"]), ("nova tentativa", "agendada"))
                self.assertEqual(view.display_status(p), "nova tentativa")
                self.assertEqual(publisher.parse(p["next_try_at"]), now + timedelta(minutes=config.RETRY_MINUTES[i]))
                now = publisher.parse(p["next_try_at"])
        self.assertEqual((result, self.post(pid)["status"]), ("falhou", "falhou"))

    def test_erro_do_conteudo_falha_na_hora_com_a_mensagem_do_google(self):
        pid = self.new_post()
        fake = FakeClient(create_errors=[GoogleError("Google respondeu 400: link proibido", status=400)])
        self.assertEqual(publisher.publish_one(self.db, pid, fake, NOW), "falhou")
        p = self.post(pid)
        self.assertEqual((p["error_kind"], p["error"]), ("google", "Google respondeu 400: link proibido"))

    def test_login_vencido_fica_marcado(self):
        pid = self.new_post()
        publisher.publish_one(self.db, pid, FakeClient(create_errors=[TokenError()]), NOW)
        self.assertEqual(self.post(pid)["error_kind"], "login")

    def test_nunca_publica_em_dobro(self):
        """O Google criou a postagem mas a resposta foi erro: a nova tentativa adota a que ja existe."""
        pid = self.new_post()
        err = GoogleError("500", status=500, retryable=True)
        err.created_anyway = True
        fake = FakeClient(create_errors=[err])
        publisher.publish_one(self.db, pid, fake, NOW)
        later = publisher.parse(self.post(pid)["next_try_at"])
        self.assertEqual(publisher.publish_one(self.db, pid, fake, later), "publicada")
        self.assertEqual(fake.count("create"), 1)
        self.assertEqual(len(fake.created), 1)

    def test_foto_nao_sobe_de_novo_na_nova_tentativa(self):
        token = images.save(photo())["token"]
        pid = self.new_post(image=token)
        fake = FakeClient(create_errors=[GoogleError("503", status=503, retryable=True)])
        publisher.publish_one(self.db, pid, fake, NOW)
        publisher.publish_one(self.db, pid, fake, publisher.parse(self.post(pid)["next_try_at"]))
        self.assertEqual(fake.count("upload"), 1)
        self.assertEqual(self.post(pid)["status"], "publicada")

    def test_foto_ainda_processando_tenta_depois(self):
        token = images.save(photo())["token"]
        pid = self.new_post(image=token)
        fake = FakeClient(media_urls=["https://lh3.googleusercontent.com/gpu-csl/x"])
        self.assertEqual(publisher.publish_one(self.db, pid, fake, NOW, lambda s: None), "nova tentativa")
        self.assertEqual(fake.count("create"), 0)

    def test_so_um_pega_a_postagem(self):
        pid = self.new_post()
        self.assertIsNotNone(storage.claim_post(self.db, pid, publisher.iso(NOW)))
        self.assertIsNone(storage.claim_post(self.db, pid, publisher.iso(NOW)))
        self.assertIsNone(publisher.publish_one(self.db, pid, FakeClient(), NOW))

    def test_passada_publica_so_as_vencidas(self):
        vencida, futura = self.new_post(NOW - timedelta(minutes=3)), self.new_post(NOW + timedelta(hours=1))
        fake = FakeClient()
        publisher.run_pass(self.db, fake, NOW)
        self.assertEqual((self.post(vencida)["status"], self.post(futura)["status"]), ("publicada", "agendada"))

    def test_vencida_ha_mais_de_um_dia_espera_o_usuario(self):
        pid = self.new_post(NOW - timedelta(hours=config.LATE_HOLD_HOURS + 1))
        fake = FakeClient()
        publisher.run_pass(self.db, fake, NOW)
        self.assertEqual(self.post(pid)["status"], "atrasada")
        self.assertEqual(fake.count("create"), 0)
        self.assertEqual(publisher.publish_one(self.db, pid, fake, NOW, manual=True), "publicada")

    def test_tentativa_interrompida_volta_para_a_fila(self):
        pid = self.new_post(NOW - timedelta(hours=1))
        storage.update_post(self.db, pid, status="publicando",
                            last_try_at=publisher.iso(NOW - timedelta(minutes=config.STUCK_MINUTES + 1)),
                            first_try_at=publisher.iso(NOW - timedelta(minutes=20)), attempts=1)
        fake = FakeClient()
        publisher.run_pass(self.db, fake, NOW)
        self.assertEqual(self.post(pid)["status"], "publicada")
        self.assertEqual(fake.count("recent"), 1)  # conferiu se a tentativa interrompida ja tinha publicado

    def test_estado_no_google_e_relido(self):
        ok, recusada = self.new_post(), self.new_post()
        publisher.publish_one(self.db, ok, FakeClient(), NOW)
        publisher.publish_one(self.db, recusada, FakeClient(), NOW)
        storage.update_post(self.db, recusada, post_name="accounts/1/locations/1/localPosts/9")
        live = FakeClient(state="LIVE")
        with mock.patch.object(live, "get_post", side_effect=lambda n: {"state": "REJECTED" if n.endswith("/9") else "LIVE"}):
            publisher.refresh_states(self.db, live, NOW)
        self.assertEqual((self.post(ok)["status"], self.post(ok)["google_state"]), ("publicada", "LIVE"))
        self.assertEqual(self.post(recusada)["status"], "recusada")

    def test_registro_da_passada(self):
        self.new_post(NOW - timedelta(minutes=1))
        log = publisher.run_scheduled(self.db, FakeClient(), NOW)
        self.assertTrue(any("publicada" in line for line in log))
        self.assertEqual(publisher.last_run(), NOW)
        with publisher.single_run() as ok:
            self.assertTrue(ok)
            self.assertEqual(publisher.run_scheduled(self.db, FakeClient(), NOW), ["outra passada em andamento"])


class LinkDefinitivoTest(unittest.TestCase):
    def test_provisorio_nao_serve(self):
        self.assertIsNone(definitive_url({"googleUrl": "https://lh3.googleusercontent.com/gpu-csl/AM3"}))
        self.assertIsNone(definitive_url({"googleUrl": "http://x"}))
        self.assertIsNone(definitive_url({}))
        self.assertEqual(definitive_url({"googleUrl": "https://lh3.googleusercontent.com/grass-cs/A=s0"}),
                         "https://lh3.googleusercontent.com/grass-cs/A=s0")


# ---------------------------------------------------------------------------
# Alerta da ultima postagem (item 29 da Completa)
# ---------------------------------------------------------------------------

class AlertaTest(Base):
    def raw_post(self, days_ago):
        self.put_raw({"collectedAt": NOW.isoformat(), "errors": [],
                      "localPosts": [{"createTime": (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")}]})

    def test_niveis(self):
        self.assertEqual(view.last_post_alert(self.db, "locations/1", NOW)["level"], "sem_postagem")
        self.raw_post(10)
        a = view.last_post_alert(self.db, "locations/1", NOW)
        self.assertEqual((a["level"], a["last_days"]), ("vai_vencer", 10))
        self.new_post(NOW + timedelta(days=5))
        self.assertIsNone(view.last_post_alert(self.db, "locations/1", NOW)["level"])

    def test_vencido(self):
        self.raw_post(40)
        self.assertEqual(view.last_post_alert(self.db, "locations/1", NOW)["level"], "vencido")

    def test_publicada_pelo_app_conta(self):
        pid = self.new_post(NOW - timedelta(days=2))
        storage.update_post(self.db, pid, status="publicada", published_at=publisher.iso(NOW - timedelta(days=2)))
        self.assertEqual(view.last_post_alert(self.db, "locations/1", NOW)["last_days"], 2)


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------

def client():
    return TestClient(webapp.app, base_url="http://127.0.0.1:8000")


class TelasTest(Base):
    def setUp(self):
        super().setUp()
        self.fake = FakeClient()
        for p in (mock.patch.object(postagens_web, "client_factory", lambda: self.fake),
                  mock.patch.object(postagens_web, "start_publish", postagens_web.publish_now),
                  mock.patch.object(publisher, "now_utc", lambda: NOW),
                  mock.patch.object(postagens_web, "now_utc", lambda: NOW),
                  mock.patch.object(launchd, "plist_path", lambda: os.path.join(self.tmp.name, "agente.plist"))):
            p.start()
            self.addCleanup(p.stop)

    def save(self, **kw):
        data = {"local": "locations/1", "texto": "Nova novidade", "botao": "BOOK", "url": "https://wa.me/55",
                "quando": "agendar", "data_hora": "2026-10-20T09:00"}
        data.update(kw)
        return client().post("/postagens/salvar", data=data, headers=ORIGIN, follow_redirects=False)

    def test_agendar_aparece_no_calendario_e_na_lista(self):
        r = self.save()
        self.assertEqual(r.status_code, 303)
        self.assertIn("mes=2026-10", r.headers["location"])
        cal = client().get(r.headers["location"]).text
        self.assertIn("Postagem salva na fila", cal)
        self.assertIn("Nova novidade", cal)
        self.assertIn(">09:00", cal)
        lista = client().get("/postagens?local=locations/1&vista=lista").text
        self.assertIn("20/10/2026 09:00", lista)
        self.assertIn("Reservar", lista)

    def test_erro_de_validacao_volta_com_o_que_foi_digitado(self):
        r = self.save(texto="Meu texto", url="")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Informe o link do botão", r.text)
        self.assertIn("Meu texto", r.text)

    def test_publicar_agora(self):
        r = self.save(quando="agora", data_hora="")
        self.assertEqual(r.status_code, 303)
        page = client().get(r.headers["location"]).text
        self.assertIn("Publicada em", page)
        self.assertIn("Ver no Google", page)
        self.assertEqual(self.fake.count("create"), 1)
        # publicada: nao edita nem apaga por aqui
        pid = int(r.headers["location"].split("=")[1])
        self.assertEqual(self.save(id=str(pid)).status_code, 409)
        self.assertEqual(client().post(f"/postagens/apagar?id={pid}", headers=ORIGIN).status_code, 409)

    def test_editar_e_apagar(self):
        self.save()
        pid = storage.list_posts(self.db, "locations/1")[0]["id"]
        self.assertIn("Editar postagem", client().get(f"/postagens/editar?id={pid}").text)
        self.assertEqual(self.save(id=str(pid), texto="Texto novo").status_code, 303)
        self.assertEqual(self.post(pid)["summary"], "Texto novo")
        self.assertEqual(client().post(f"/postagens/apagar?id={pid}", headers=ORIGIN, follow_redirects=False).status_code, 303)
        self.assertIsNone(self.post(pid))

    def test_editar_a_que_falhou_da_nova_chance_e_troca_a_foto(self):
        token = images.save(photo())["token"]
        pid = self.new_post(image=token, status="falhou")
        storage.update_post(self.db, pid, attempts=5, media_name="m/1", image_url="https://x", error="erro")
        outra = images.save(photo(800, 600))["token"]
        self.save(id=str(pid), imagem=outra)
        p = self.post(pid)
        self.assertEqual((p["status"], p["attempts"], p["media_name"], p["error"], p["image"]),
                         ("agendada", 0, None, None, outra))

    def test_enviar_imagem(self):
        r = client().post("/postagens/imagem", content=photo(), headers={**ORIGIN, "content-type": "image/jpeg"})
        self.assertEqual(r.status_code, 200)
        token = r.json()["token"]
        self.assertRegex(token, r"^[0-9a-f]{32}$")
        img = client().get(f"/postagens/imagem/{token}")
        self.assertEqual((img.status_code, img.headers["content-type"]), (200, "image/jpeg"))
        ruim = client().post("/postagens/imagem", content=b"<script>", headers=ORIGIN)
        self.assertEqual(ruim.status_code, 400)
        self.assertIn("Não foi possível ler", ruim.json()["erro"])
        self.assertEqual(client().get("/postagens/imagem/..%2F..%2Fgbp.db").status_code, 404)

    def test_post_de_outro_site_e_recusado(self):
        for url in ("/postagens/salvar", "/postagens/imagem", "/postagens/apagar?id=1", "/postagens/publicar?id=1"):
            r = client().post(url, content=b"x", headers={"origin": "https://malicioso.com"})
            self.assertEqual(r.status_code, 403, url)

    def test_texto_sai_escapado(self):
        self.save(texto="<script>alert(1)</script>")
        pid = storage.list_posts(self.db, "locations/1")[0]["id"]
        for page in (client().get(f"/postagens/editar?id={pid}").text,
                     client().get("/postagens?local=locations/1&vista=lista").text,
                     client().get("/postagens?local=locations/1&mes=2026-10").text):
            self.assertNotIn("<script>alert", page)
            self.assertIn("&lt;script&gt;", page)

    def test_link_publicado_so_vira_href_se_for_https(self):
        pid = self.new_post(status="publicada")
        storage.update_post(self.db, pid, search_url="javascript:alert(1)", published_at=publisher.iso(NOW))
        self.assertNotIn('href="javascript', client().get(f"/postagens/editar?id={pid}").text)

    def test_avisos_de_publicador_desligado_e_login(self):
        page = client().get("/postagens?local=locations/1").text
        self.assertIn("publicador automático não está ligado", page)
        pid = self.new_post(status="falhou")
        storage.update_post(self.db, pid, error_kind="login", error="login")
        self.assertIn("login do Google parou de funcionar", client().get("/postagens?local=locations/1").text)

    def test_botao_na_tela_principal(self):
        self.analysis_html = client().get("/?local=locations/1").text
        self.assertIn('href="/postagens?local=locations/1"', self.analysis_html)


# ---------------------------------------------------------------------------
# Travas
# ---------------------------------------------------------------------------

class TravasTest(unittest.TestCase):
    def test_so_posts_google_api_escreve_no_google(self):
        """Nenhum outro arquivo faz POST, PATCH, PUT ou DELETE para o Google (CLAUDE.md, secao 15 e 17)."""
        write = re.compile(r"requests\.(post|patch|put|delete)\(|\.request\(\s*\"(POST|PATCH|PUT|DELETE)\"|"
                           r"_call\(\s*\"(POST|PATCH|PUT|DELETE)\"")
        offenders = []
        for root, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in (".venv", "tests", "__pycache__", ".git", "data", "extension",
                                                    ".playwright-mcp", "node_modules")]
            for name in files:
                if name.endswith(".py"):
                    path = os.path.join(root, name)
                    with open(path, encoding="utf-8") as f:
                        if write.search(f.read()):
                            offenders.append(os.path.relpath(path, HERE))
        self.assertEqual(offenders, [os.path.join("posts", "google_api.py")])

    def test_google_api_nao_apaga_nada_no_google(self):
        with open(os.path.join(HERE, "posts", "google_api.py"), encoding="utf-8") as f:
            self.assertNotIn('"DELETE"', f.read())

    def test_agente_do_macos(self):
        p = launchd.plist_content(python="/py", project="/proj")
        self.assertEqual(p["ProgramArguments"], ["/py", "/proj/coletar.py", "publicar"])
        self.assertEqual((p["StartInterval"], p["RunAtLoad"]), (300, True))
        self.assertTrue(p["StandardOutPath"].startswith("/proj/data/logs/"))


if __name__ == "__main__":
    unittest.main()
