"""Perfil normalizado (secao 7 do CLAUDE.md). Funcao pura: JSON bruto entra, perfil sai."""

from urllib.parse import quote_plus

STARS = {"FIVE": 5, "FOUR": 4, "THREE": 3, "TWO": 2, "ONE": 1}


def _time(t):
    t = t or {}
    return f"{t.get('hours', 0):02d}:{t.get('minutes', 0):02d}"


def _hours(regular):
    """{'MONDAY': [['07:00', '16:00']], ...}; dias fechados nao aparecem."""
    out = {}
    for p in (regular or {}).get("periods", []):
        out.setdefault(p["openDay"], []).append([_time(p.get("openTime")), _time(p.get("closeTime"))])
    return out


def _date(d):
    if not d or "year" not in d:
        return None
    return f"{d['year']:04d}-{d.get('month', 1):02d}-{d.get('day', 1):02d}"


def _address(a):
    a = a or {}
    partes = list(a.get("addressLines", [])) + [a.get("sublocality"), a.get("locality"),
                                                  a.get("administrativeArea"), a.get("postalCode")]
    return ", ".join(p for p in partes if p)


def _service_name(item):
    free = item.get("freeFormServiceItem")
    if free:
        return free.get("label", {}).get("displayName")
    return item.get("structuredServiceItem", {}).get("serviceTypeId")


def _media(items):
    return [{
        "format": m.get("mediaFormat"),
        "category": (m.get("locationAssociation") or {}).get("category"),
        "createdAt": m.get("createTime"),
        "url": m.get("googleUrl"),
    } for m in items or []]


def _first_url(media, category):
    return next((m["url"] for m in media if m["category"] == category and m["url"]), "")


def normalize(raw):
    info = raw["info"]
    reviews = [{
        "rating": STARS.get(r.get("starRating"), 0),
        "createdAt": r.get("createTime"),
        "hasComment": bool((r.get("comment") or "").strip()),
        "replied": bool((r.get("reviewReply") or {}).get("comment")),
    } for r in raw.get("reviews") or []]
    media = _media(raw.get("media"))
    media_cli = _media(raw.get("mediaCustomers"))
    cats = info.get("categories", {})
    addr = info.get("storefrontAddress", {})
    meta = info.get("metadata", {})
    nome = info.get("title", "")
    cidade = addr.get("locality", "")

    # Decisao Fase 0: contagem, media e distribuicao vem da lista de avaliacoes.
    distribuicao = [sum(1 for r in reviews if r["rating"] == n) for n in (5, 4, 3, 2, 1)]
    nota = round(sum(r["rating"] for r in reviews) / len(reviews), 1) if reviews else 0.0
    total_api = (raw.get("reviewsSummary") or {}).get("totalReviewCount")

    return {
        "location": {
            "id": raw["location"],
            "name": nome,
            "category": (cats.get("primaryCategory") or {}).get("displayName", ""),
            "city": cidade,
            "address": _address(addr),
            "phone": (info.get("phoneNumbers") or {}).get("primaryPhone", ""),
            "website": info.get("websiteUri", ""),
            "description": (info.get("profile") or {}).get("description", ""),
            "rating": nota,
            "reviewCount": len(reviews),
            "starDistribution": distribuicao,  # posicao 0 = 5 estrelas ... posicao 4 = 1 estrela
            "hours": _hours(info.get("regularHours")),
            "mapsUrl": meta.get("mapsUri", ""),
            # (hipotese) o Google nao devolve link da Pesquisa; busca pelo nome e cidade.
            "searchUrl": "https://www.google.com/search?q=" + quote_plus(f"{nome} {cidade}".strip()),
            "logoUrl": _first_url(media, "PROFILE"),  # decisao Fase 0: logo = PROFILE
            "coverUrl": _first_url(media, "COVER"),
            # Alem do contrato: dados que o motor de nota vai precisar.
            "additionalCategories": [c.get("displayName", "") for c in cats.get("additionalCategories", [])],
            "specialHours": [{"start": _date(p.get("startDate")), "end": _date(p.get("endDate")),
                              "closed": bool(p.get("closed"))}
                             for p in (info.get("specialHours") or {}).get("specialHourPeriods", [])],
            "services": [n for n in map(_service_name, info.get("serviceItems", [])) if n],
            "openingDate": _date((info.get("openInfo") or {}).get("openingDate")),
            # A API omite booleanos falsos: sem canModifyServiceList a categoria nao aceita lista de servicos.
            # None = sem `metadata` na leitura, nao da para saber.
            "servicesEditable": bool(meta.get("canModifyServiceList")) if "metadata" in info else None,
        },
        "reviews": reviews,
        "reviewsComplete": total_api is None or total_api == len(reviews),
        "media": media,
        "customerMedia": media_cli,
        "posts": [{"type": p.get("topicType"), "createdAt": p.get("createTime")}
                  for p in raw.get("localPosts") or []],
        "collectionErrors": raw.get("errors", {}),
        "collectedAt": raw["collectedAt"],
    }
