"""Coleta: fala com o Google e devolve o JSON bruto de um local (sem interpretar nada)."""

from datetime import datetime, timezone

import gbp_auth as g

READ_MASK = ("name,title,storefrontAddress,phoneNumbers,categories,websiteUri,regularHours,"
             "specialHours,profile,serviceItems,openInfo,metadata,latlng")


def _pages(api, path, key, params):
    """Percorre todas as paginas. Devolve (itens, primeira pagina sem a lista) ou {'_erro'}."""
    params = dict(params)
    items, head, vistos = [], None, set()
    while True:
        data = g.get(api, path, params, soft=True)
        if "_erro" in data:
            return data, None
        if head is None:
            head = {k: v for k, v in data.items() if k != key}
        pagina = data.get(key, [])
        items += pagina
        token = data.get("nextPageToken")
        # media/customers devolve paginas vazias com o mesmo token para sempre: parar nesse caso.
        if not token or not pagina or token in vistos:
            return items, head
        vistos.add(token)
        params["pageToken"] = token


def fetch_raw(account, location):
    """JSON bruto de um local. Falha parcial vai para raw['errors'], nunca vira lista vazia."""
    v4 = f"{account}/{location}"
    errors = {}

    def section(nome, api, path, key, params):
        itens, head = _pages(api, path, key, params)
        if isinstance(itens, dict):
            errors[nome] = itens["_erro"]
            return None, None
        return itens, head

    info = g.get("info", location, {"readMask": READ_MASK})
    reviews, reviews_head = section("reviews", "v4", f"{v4}/reviews", "reviews", {"pageSize": 50})
    media, _ = section("media", "v4", f"{v4}/media", "mediaItems", {"pageSize": 100})
    media_cli, _ = section("mediaCustomers", "v4", f"{v4}/media/customers", "mediaItems", {"pageSize": 100})
    posts, _ = section("localPosts", "v4", f"{v4}/localPosts", "localPosts", {"pageSize": 100})

    return {
        "collectedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "account": account,
        "location": location,
        "info": info,
        "reviews": reviews,
        "reviewsSummary": reviews_head,  # averageRating / totalReviewCount, so para conferir
        "media": media,
        "mediaCustomers": media_cli,
        "localPosts": posts,
        "errors": errors,
    }
