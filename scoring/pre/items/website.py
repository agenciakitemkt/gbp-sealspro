from urllib.parse import urlparse

from scoring.base import Item, Outcome
from scoring.pre.base import cfg


def is_social(url):
    """O primeiro nome do endereco (sem www) e de uma rede social: instagram.com e instagram.com.br contam."""
    host = urlparse(url if "//" in url else f"//{url}").hostname or ""
    labels = [p for p in host.lower().split(".") if p]
    if labels and labels[0] in ("www", "m"):
        labels = labels[1:]
    return bool(labels) and labels[0] in cfg("website")["social_names"]


def evaluate(profile, now):
    url = (profile["location"].get("website") or "").strip()
    if not url:
        return Outcome(0, "O perfil não tem site cadastrado.", {})
    if is_social(url):
        return Outcome(cfg("website")["social_score"],
                       "O site cadastrado é uma página de rede social ({current}), e não um site próprio.",
                       {"current": url})
    return Outcome(100, "Site próprio cadastrado: {current}.", {"current": url})


ITEM = Item("website", "website", "Website", (), evaluate)
