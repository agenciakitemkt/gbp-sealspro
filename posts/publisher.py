"""Publicador: leva ao Google as postagens vencidas da fila (CLAUDE.md, secao 17).

Roda de duas formas: pelo agendador do macOS (launchd, `coletar.py publicar`, a cada 5 minutos e ao acordar o Mac) e
pela tela, no "Publicar agora". As duas podem rodar ao mesmo tempo: cada postagem e "pega" com uma troca atomica de
status no banco (storage.claim_post), entao so uma delas publica.

Regras:
- Nunca publicar em dobro: se ja houve tentativa antes (first_try_at), confere no Google se uma postagem com o mesmo
  texto ja foi criada desde entao, e adota essa em vez de criar outra.
- Erro passageiro (rede, 429, 5xx, foto ainda processando, login): nova tentativa em 2, 5, 15, 30 min; depois de
  MAX_ATTEMPTS, "falhou". Erro do conteudo (4xx): "falhou" na hora, com a mensagem do Google.
- Agendada vencida ha mais de LATE_HOLD_HOURS sem nenhuma tentativa (Mac desligado): nao sai sozinha. Fica
  "atrasada" ate o usuario publicar ou reagendar (uma postagem de data comemorativa nao deve sair dias depois).
"""

import fcntl
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import storage
from posts import config, images
from posts.google_api import GoogleError, TokenError, definitive_url


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse(value):
    return datetime.fromisoformat(value) if value else None


class MediaNotReady(GoogleError):
    def __init__(self):
        super().__init__("O Google ainda está processando a foto.", retryable=True)


def build_body(post, image_url):
    body = {"languageCode": "pt-BR", "topicType": "STANDARD", "summary": post["summary"]}
    if post["cta_type"]:
        body["callToAction"] = {"actionType": post["cta_type"]}
        if post["cta_type"] not in config.CTA_WITHOUT_URL:
            body["callToAction"]["url"] = post["cta_url"]
    if image_url:
        body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": image_url}]
    return body


def _same_text(a, b):
    return " ".join((a or "").split()) == " ".join((b or "").split())


def find_existing(client, location, post):
    """Postagem com o mesmo texto criada no Google desde a primeira tentativa (menos uma margem), ou None."""
    since = parse(post["first_try_at"]) - timedelta(minutes=config.DUPLICATE_WINDOW_MINUTES)
    for p in client.recent_posts(location["account_id"], location["id"]):
        created = p.get("createTime")
        if created and _same_text(p.get("summary"), post["summary"]) \
                and datetime.fromisoformat(created.replace("Z", "+00:00")) >= since:
            return p
    return None


def _wait_media(client, media_name, sleep):
    for i in range(config.MEDIA_WAIT_TRIES):
        url = definitive_url(client.get_media(media_name))
        if url:
            return url
        if i < config.MEDIA_WAIT_TRIES - 1:
            sleep(config.MEDIA_WAIT_SECONDS)
    raise MediaNotReady()


def _published(db, post, created, now):
    state = created.get("state") or ""
    db_status = "recusada" if state == "REJECTED" else "publicada"
    storage.update_post(db, post["id"], status=db_status, published_at=iso(now), post_name=created.get("name"),
                        search_url=created.get("searchUrl"), google_state=state, next_try_at=None,
                        error="O Google recusou a postagem." if state == "REJECTED" else None,
                        error_kind="recusa" if state == "REJECTED" else None)
    return db_status


def _failed(db, post, error, now, manual):
    """Erro numa tentativa: agenda a proxima ou desiste."""
    kind = "login" if isinstance(error, TokenError) else ("google" if not error.retryable else "passageiro")
    attempts = post["attempts"]
    if error.retryable and not manual and attempts < config.MAX_ATTEMPTS:
        wait = config.RETRY_MINUTES[min(attempts, len(config.RETRY_MINUTES)) - 1]
        storage.update_post(db, post["id"], status="agendada", next_try_at=iso(now + timedelta(minutes=wait)),
                            error=str(error), error_kind=kind)
        return "nova tentativa"
    storage.update_post(db, post["id"], status="falhou", next_try_at=None, error=str(error), error_kind=kind)
    return "falhou"


def publish_one(db, post_id, client, now=None, sleep=time.sleep, manual=False):
    """Tenta publicar uma postagem. Devolve o resultado ('publicada', 'recusada', 'nova tentativa', 'falhou') ou
    None se outra execucao ja a pegou."""
    now = now or now_utc()
    post = storage.claim_post(db, post_id, iso(now))
    if post is None:
        return None
    location = next((r for r in storage.list_locations(db) if r["id"] == post["location_id"]), None)
    if location is None:
        storage.update_post(db, post_id, status="falhou", error="Local não encontrado.", error_kind="google")
        return "falhou"
    try:
        if post["first_try_at"] != iso(now):  # ja houve tentativa antes desta: pode ter criado a postagem
            existing = find_existing(client, location, post)
            if existing:
                return _published(db, post, existing, now)
        image_url = None
        if post["image"]:
            if not post["media_name"]:
                media = client.upload_photo(location["account_id"], location["id"], images.read(post["image"]))
                storage.update_post(db, post_id, media_name=media["name"])  # gravado ja: a nova tentativa nao sobe de novo
                post["media_name"] = media["name"]
            image_url = _wait_media(client, post["media_name"], sleep)
            storage.update_post(db, post_id, image_url=image_url)
        created = client.create_post(location["account_id"], location["id"], build_body(post, image_url))
        return _published(db, post, created, now)
    except GoogleError as e:
        return _failed(db, post, e, now, manual)
    except (OSError, images.ImageError):
        storage.update_post(db, post_id, status="falhou", error="A imagem da postagem não foi encontrada no "
                            "computador. Escolha a imagem de novo.", error_kind="imagem")
        return "falhou"


def refresh_states(db, client, now):
    """Rele no Google as publicadas ainda 'processando' (viram 'no ar' ou 'recusada')."""
    since = iso(now - timedelta(days=config.REFRESH_DAYS))
    out = []
    for post in storage.posts_where(db, "status='publicada' AND COALESCE(google_state,'') != 'LIVE' "
                                        "AND post_name IS NOT NULL AND published_at >= ?", (since,)):
        try:
            state = client.get_post(post["post_name"]).get("state") or ""
        except GoogleError:
            continue
        if state != post["google_state"]:
            fields = {"google_state": state}
            if state == "REJECTED":
                fields.update(status="recusada", error="O Google recusou a postagem.", error_kind="recusa")
            storage.update_post(db, post["id"], **fields)
            out.append((post["id"], state))
    return out


def run_pass(db, client, now=None, sleep=time.sleep):
    """Uma passada do publicador. Devolve o que fez, para o log."""
    now = now or now_utc()
    log = []
    stuck = iso(now - timedelta(minutes=config.STUCK_MINUTES))
    for post in storage.posts_where(db, "status='publicando' AND last_try_at < ?", (stuck,)):
        storage.update_post(db, post["id"], status="agendada", next_try_at=None,
                            error="A tentativa anterior foi interrompida.", error_kind="passageiro")
        log.append(f"#{post['id']} interrompida: volta para a fila")
    late = now - timedelta(hours=config.LATE_HOLD_HOURS)
    for post in storage.posts_where(db, "status='agendada' AND scheduled_at <= ? "
                                        "AND (next_try_at IS NULL OR next_try_at <= ?) ORDER BY scheduled_at",
                                    (iso(now), iso(now))):
        if post["attempts"] == 0 and parse(post["scheduled_at"]) < late:
            storage.update_post(db, post["id"], status="atrasada",
                                error="O horário passou há mais de 24 horas sem o computador ligado. "
                                      "Publique agora ou escolha outra data.", error_kind="atraso")
            log.append(f"#{post['id']} atrasada: espera decisão")
            continue
        log.append(f"#{post['id']} {publish_one(db, post['id'], client, now, sleep)}")
    for post_id, state in refresh_states(db, client, now):
        log.append(f"#{post_id} estado no Google: {state}")
    removed = images.remove_orphans(storage.images_in_use(db), now.timestamp())
    if removed:
        log.append(f"{len(removed)} imagem(ns) sem uso apagada(s)")
    return log


# ---------------------------------------------------------------------------
# Execucao pelo agendador (uma passada por vez, com registro da ultima)
# ---------------------------------------------------------------------------

def logs_dir():
    return os.path.join(storage.DATA, "logs")


def heartbeat_path():
    return os.path.join(logs_dir(), "publicador-ultimo.txt")


@contextmanager
def single_run():
    """Trava de arquivo: se uma passada ainda estiver rodando, a outra nao faz nada (yield False)."""
    os.makedirs(logs_dir(), exist_ok=True)
    with open(os.path.join(logs_dir(), "publicador.lock"), "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def run_scheduled(db, client, now=None):
    """O que o launchd chama. Grava o registro em data/logs/ e a hora da ultima passada (a tela mostra)."""
    now = now or now_utc()
    with single_run() as ok:
        if not ok:
            return ["outra passada em andamento"]
        log = run_pass(db, client, now)
        with open(heartbeat_path(), "w", encoding="utf-8") as f:
            f.write(iso(now))
        if log:
            with open(os.path.join(logs_dir(), "publicador.log"), "a", encoding="utf-8") as f:
                f.writelines(f"{iso(now)} {line}\n" for line in log)
        return log


def last_run():
    try:
        with open(heartbeat_path(), encoding="utf-8") as f:
            return parse(f.read().strip())
    except (OSError, ValueError):
        return None
