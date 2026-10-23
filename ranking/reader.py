"""Leitura de um ponto da grade: a resposta da busca do Google Maps (tbm=map, fonte D da secao 13) feita pela extensao
naquele ponto. Resultados em [64]; anuncio = entrada com 6 posicoes (sem dados do local); o resto e o local em [64][i][1].
Nunca levanta excecao por causa do conteudo: resposta ilegivel = None."""

from collector_pre.maps_reader import _json, cid_from_ftid, g

from ranking.config import RESULTS_PER_POINT


def _num(v, kind):
    return v if isinstance(v, kind) and not isinstance(v, bool) else None


def _text(v, limit=200):
    return v[:limit] if isinstance(v, str) else None


def read_point(raw):
    """Texto (ou JSON) da busca -> lista ordenada dos resultados organicos (ate 20), cada um com placeId, cid, name,
    rating, reviews, category, address, lat e lng. Lista vazia = busca sem resultados. None = formato inesperado."""
    results = g(_json(raw), 64)
    if results is None and isinstance(_json(raw), list):
        return []  # busca lida, sem a lista de resultados: nenhum local naquele ponto
    if not isinstance(results, list):
        return None
    out, seen = [], set()
    for e in results:
        p = g(e, 1)
        if not isinstance(p, list) or (isinstance(e, list) and len(e) == 6):
            continue  # anuncio (patrocinado nao conta, como no GBP Check)
        place_id, cid = _text(g(p, 78)), cid_from_ftid(g(p, 10))
        key = place_id or cid
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"placeId": place_id, "cid": cid, "name": _text(g(p, 11)) or "",
                    "rating": _num(g(p, 4, 7), (int, float)), "reviews": _num(g(p, 4, 8), int),
                    "category": _text(g(p, 13, 0), 100), "address": _text(g(p, 39)),
                    "lat": _num(g(p, 9, 2), (int, float)), "lng": _num(g(p, 9, 3), (int, float))})
        if len(out) == RESULTS_PER_POINT:
            break
    return out


def same_place(result, place_id, cid):
    return bool((place_id and result.get("placeId") == place_id) or (cid and result.get("cid") == cid))


def position(results, place_id, cid):
    """Posicao (1 a 20) do local na lista, ou None se nao aparece."""
    for n, r in enumerate(results or [], 1):
        if same_place(r, place_id, cid):
            return n
    return None
