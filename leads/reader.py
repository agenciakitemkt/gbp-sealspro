"""Leitura de uma pagina da busca do Google Maps (tbm=map, fonte D da secao 13) feita pela extensao num ponto: cada
resultado organico vira um lead com os dados do perfil que a busca traz (o mesmo formato de local da fonte A, em
[64][i][1]). A busca nao traz a descricao, e as vezes nao traz a quantidade de avaliacoes (ver CLAUDE.md, 18).
Nunca levanta excecao por causa do conteudo: resposta ilegivel = None. Todo texto e nao confiavel."""

from collector_pre.maps_reader import _json, cid_from_ftid, g


def _num(v, kind):
    return v if isinstance(v, kind) and not isinstance(v, bool) else None


def _text(v, limit=300):
    return v.strip()[:limit] if isinstance(v, str) and v.strip() else ""


def _hours(raw):
    out = {}
    for day in raw if isinstance(raw, list) else []:
        if isinstance(g(day, 0), str):
            out[day[0][:20]] = [h[0][:40] for h in (g(day, 3) or []) if isinstance(g(h, 0), str)][:6]
    return out


def read_lead(p):
    """Local da busca ([64][i][1]) -> lead, ou None sem identificador."""
    place_id, cid = _text(g(p, 78), 100), cid_from_ftid(g(p, 10)) or ""
    key = place_id or cid
    name = _text(g(p, 11), 200)
    if not key or not name:
        return None
    rating, count = _num(g(p, 4, 7), (int, float)), _num(g(p, 4, 8), int)
    if g(p, 4) is None:  # sem o bloco de avaliacoes = nenhuma avaliacao (busca real de 2026-10-14: 76 de 278)
        count = 0
    lat, lng = _num(g(p, 9, 2), (int, float)), _num(g(p, 9, 3), (int, float))
    return {
        "key": key, "placeId": place_id, "cid": cid, "name": name,
        "categories": [c[:100] for c in (g(p, 13) or []) if isinstance(c, str)][:10],
        "address": _text(g(p, 39)),
        "phone": _text(g(p, 178, 0, 0), 40), "website": _text(g(p, 7, 0), 500),
        "rating": rating, "reviews": count,
        # Link "reivindicar esta empresa" em [49] = nao verificado (como na Pre Analise, maps_reader.read_place)
        "verified": g(p, 49) is None,
        "hours": _hours(g(p, 203, 0)),
        "logo": _text(g(p, 157), 500),
        "lat": lat, "lng": lng,
    }


def read_page(raw):
    """Texto (ou JSON) da busca -> (lista de leads na ordem da pagina, quantos resultados organicos vieram).
    Lista vazia = busca sem resultados. None = formato inesperado."""
    data = _json(raw)
    results = g(data, 64)
    if results is None and isinstance(data, list):
        return [], 0
    if not isinstance(results, list):
        return None
    out, seen, organic = [], set(), 0
    for e in results:
        p = g(e, 1)
        if not isinstance(p, list) or (isinstance(e, list) and len(e) == 6):
            continue  # anuncio
        organic += 1
        lead = read_lead(p)
        if lead and lead["key"] not in seen:
            seen.add(lead["key"])
            out.append(lead)
    return out, organic
