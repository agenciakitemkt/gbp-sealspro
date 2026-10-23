"""Regiao da busca (cidade, bairro, rua) -> retangulo, pelo Nominatim do OpenStreetMap (gratuito, uso leve, com
User-Agent proprio e uma consulta por vez), como o centro dos perfis sem endereco no Ranking (ranking/geocode.py)."""

import requests

from ranking.geocode import NOMINATIM, USER_AGENT


def find_region(text, get=requests.get):
    """Texto -> {"name", "lat", "lng", "south", "north", "west", "east"} ou None (nao achou ou sem internet)."""
    try:
        r = get(NOMINATIM, params={"q": text, "format": "jsonv2", "limit": 1, "countrycodes": "br"},
                headers={"User-Agent": USER_AGENT}, timeout=10)
        data = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return None
    if not data:
        return None
    try:
        hit = data[0]
        south, north, west, east = (float(v) for v in hit["boundingbox"])
        lat, lng = float(hit["lat"]), float(hit["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90 <= south <= north <= 90 and -180 <= west <= east <= 180):
        return None
    return {"name": str(hit.get("display_name") or text)[:200], "lat": lat, "lng": lng,
            "south": south, "north": north, "west": west, "east": east}
