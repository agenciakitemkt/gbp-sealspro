"""Validacao do formulario de postagem (Novidade). Pura: recebe o que veio da tela, devolve os campos ou os erros."""

from datetime import timedelta
from urllib.parse import urlparse

from posts import config, images
from posts.publisher import iso, parse
from posts.view import local_to_utc


def validate(form, now):
    """form: dict de textos da tela. Devolve (campos, erros). campos['now'] = publicar agora."""
    errors = []
    summary = (form.get("texto") or "").replace("\r\n", "\n").strip()
    if not summary:
        errors.append("Escreva o texto da postagem.")
    elif len(summary) > config.SUMMARY_MAX:
        errors.append(f"O texto passou de {config.SUMMARY_MAX} caracteres ({len(summary)}).")

    cta = form.get("botao") or ""
    url = (form.get("url") or "").strip()
    if cta not in config.CTA_LABELS:
        errors.append("Botão inválido.")
        cta = ""
    if cta in config.CTA_WITHOUT_URL:
        url = ""
    else:
        p = urlparse(url)
        if not url:
            errors.append("Informe o link do botão.")
        elif p.scheme not in ("http", "https") or not p.netloc or " " in url or len(url) > config.URL_MAX:
            errors.append("O link do botão precisa começar com https:// (ou http://) e ser um endereço válido.")

    image = form.get("imagem") or ""
    if image and not images.exists(image):
        errors.append("A imagem não foi encontrada. Envie de novo.")
        image = ""

    publish_now = form.get("quando") == "agora"
    scheduled = iso(now)
    if not publish_now:
        try:
            scheduled = local_to_utc(form.get("data_hora") or "")
        except ValueError:
            errors.append("Escolha a data e a hora da publicação.")
        else:
            when = parse(scheduled)
            if when < now - timedelta(minutes=1):
                errors.append("A data e a hora já passaram. Escolha um horário futuro ou “Publicar agora”.")
            elif when > now + timedelta(days=366):
                errors.append("Escolha uma data dentro de um ano.")
    return {"summary": summary, "cta_type": cta, "cta_url": url, "image": image, "scheduled_at": scheduled,
            "now": publish_now}, errors
