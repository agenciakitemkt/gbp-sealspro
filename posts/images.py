"""Imagem da postagem: confere, corrige e grava como JPEG em data/posts/ (fora do git).

Regravar sempre como JPEG resolve tres coisas de uma vez: o Google aceita, a orientacao da camera fica certa e os
metadados do arquivo (GPS do celular, autor) nao vao para o perfil do cliente.
"""

import io
import os
import re
import secrets
import time

from PIL import Image, ImageOps, UnidentifiedImageError

import storage
from posts import config

TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
ACCEPTED = {"JPEG", "PNG", "WEBP"}


class ImageError(ValueError):
    pass


def folder():
    """Calculada a cada uso a partir de storage.DATA (os testes isolam trocando DATA)."""
    return os.path.join(storage.DATA, "posts")


def path_for(token):
    if not TOKEN_RE.match(token or ""):
        raise ImageError("Imagem inválida.")
    return os.path.join(folder(), f"{token}.jpg")


def _encode(img, quality):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def prepare(data):
    """Bytes enviados -> (jpeg, largura, altura). ImageError com a explicacao, em portugues, se nao servir."""
    if not data:
        raise ImageError("Nenhum arquivo recebido.")
    if len(data) > config.IMAGE_UPLOAD_MAX:
        raise ImageError(f"Arquivo grande demais (máximo {config.IMAGE_UPLOAD_MAX // (1024 * 1024)} MB).")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            if fmt not in ACCEPTED:
                raise ImageError("Formato não aceito. Use JPG ou PNG.")
            if probe.width * probe.height > config.IMAGE_MAX_PIXELS:
                raise ImageError("Imagem grande demais. Reduza o tamanho antes de enviar.")
            probe.load()
            img = ImageOps.exif_transpose(probe)
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                rgba = img.convert("RGBA")
                img = Image.new("RGB", rgba.size, "white")
                img.paste(rgba, mask=rgba.getchannel("A"))
            else:
                img = img.convert("RGB")
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise ImageError("Não foi possível ler a imagem. Use um arquivo JPG ou PNG.") from None
    if min(img.size) < config.IMAGE_MIN_SIDE:
        raise ImageError(f"Imagem pequena demais ({img.width}×{img.height}). O mínimo é "
                         f"{config.IMAGE_MIN_SIDE}×{config.IMAGE_MIN_SIDE} pixels; o ideal é 1200×900.")
    if max(img.size) > config.IMAGE_MAX_SIDE:
        img.thumbnail((config.IMAGE_MAX_SIDE, config.IMAGE_MAX_SIDE), Image.LANCZOS)
    jpeg = _encode(img, 88)
    if len(jpeg) < config.IMAGE_MIN_BYTES:
        jpeg = _encode(img, 100)
    if len(jpeg) < config.IMAGE_MIN_BYTES:
        raise ImageError("Imagem simples demais: o Google recusa fotos com menos de 10 KB. Use uma foto maior.")
    quality = 80
    while len(jpeg) > config.IMAGE_MAX_BYTES and quality >= 40:
        jpeg, quality = _encode(img, quality), quality - 10
    if len(jpeg) > config.IMAGE_MAX_BYTES:
        raise ImageError("Imagem pesada demais mesmo depois de reduzir. Use outra foto.")
    return jpeg, img.width, img.height


def save(data):
    """Prepara e grava. Devolve {token, width, height}."""
    jpeg, w, h = prepare(data)
    os.makedirs(folder(), exist_ok=True)
    token = secrets.token_hex(16)
    with open(path_for(token), "wb") as f:
        f.write(jpeg)
    return {"token": token, "width": w, "height": h}


def read(token):
    with open(path_for(token), "rb") as f:
        return f.read()


def exists(token):
    try:
        return os.path.isfile(path_for(token))
    except ImageError:
        return False


def remove(token):
    try:
        os.remove(path_for(token))
    except (ImageError, FileNotFoundError):
        pass


def remove_orphans(in_use, now=None):
    """Apaga imagens enviadas e nunca usadas (ou de postagens apagadas) ha mais de ORPHAN_IMAGE_HOURS."""
    if not os.path.isdir(folder()):
        return []
    limit = (now or time.time()) - config.ORPHAN_IMAGE_HOURS * 3600
    removed = []
    for name in os.listdir(folder()):
        token, ext = os.path.splitext(name)
        full = os.path.join(folder(), name)
        if ext == ".jpg" and TOKEN_RE.match(token) and token not in in_use and os.path.getmtime(full) < limit:
            os.remove(full)
            removed.append(token)
    return removed
