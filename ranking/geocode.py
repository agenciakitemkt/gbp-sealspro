"""Centro da grade para perfis sem endereco publico (area de atendimento): o Maps nao tem pin e devolve o centro do
pais (caso real em 2026-10-11: -14,41; -51,32, zoom 4). Nesses casos o centro vem do endereco cadastrado na
conta do Google (storefrontAddress da Business Information API), convertido em coordenadas pelo Nominatim
(OpenStreetMap; gratuito, uso leve, com User-Agent proprio e uma consulta por vez)."""

import requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "gbp-sealspro/1.0 (SealsPro, uso interno)"


def _query(params, get):
    try:
        r = get(NOMINATIM, params={**params, "format": "jsonv2", "limit": 1, "countrycodes": "br"},
                headers={"User-Agent": USER_AGENT}, timeout=10)
        data = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return None
    if not data:
        return None
    try:
        lat, lng = float(data[0]["lat"]), float(data[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lng) if abs(lat) <= 90 and abs(lng) <= 180 else None


def geocode_address(address, get=requests.get):
    """storefrontAddress -> (lat, lng, precisao) ou None. Tenta a rua com numero; senao o bairro; senao a cidade."""
    if not isinstance(address, dict):
        return None
    lines = ", ".join(address.get("addressLines") or [])
    city, state = address.get("locality") or "", address.get("administrativeArea") or ""
    district, cep = address.get("sublocality") or "", address.get("postalCode") or ""
    attempts = []
    if lines and city:
        attempts.append(({"street": lines, "city": city, "state": state, "postalcode": cep}, "endereço"))
        attempts.append(({"q": f"{lines}, {district}, {city}, {state}"}, "endereço"))
    if district and city:
        attempts.append(({"q": f"{district}, {city}, {state}"}, "bairro"))
    if city:
        attempts.append(({"city": city, "state": state}, "cidade"))
    for params, precision in attempts:
        found = _query({k: v for k, v in params.items() if v}, get)
        if found:
            return found[0], found[1], precision
    return None
