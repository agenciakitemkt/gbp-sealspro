import copy
import json
import os
from datetime import datetime, timedelta

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "referencia.json")
with open(_PATH, encoding="utf-8") as f:
    _REFERENCIA = json.load(f)

NOW = datetime.fromisoformat(_REFERENCIA["collectedAt"])


def referencia():
    """Perfil normalizado anonimizado da perfil de referência (referência da seção 10 do CLAUDE.md)."""
    return copy.deepcopy(_REFERENCIA)


def days_ago(n):
    return (NOW - timedelta(days=n)).isoformat()


def run(item, profile):
    return item.evaluate(profile, NOW)


def media(fmt="PHOTO", category="ADDITIONAL", created="2026-09-30T00:00:00Z"):
    return {"format": fmt, "category": category, "createdAt": created, "url": "https://example.com/m.jpg"}


def review(rating=5, comment=True, replied=True, created=None):
    return {"rating": rating, "createdAt": created or days_ago(10), "hasComment": comment, "replied": replied}
