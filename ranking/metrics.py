"""Metricas da Analise de Ranking, como o GBP Check (conferidas na referencia de 2026-10-11, CLAUDE.md 16.1):
- ARP: posicao media nos pontos onde o local aparece;
- ATRP: posicao media em todos os pontos, contando "fora dos 20" como 21;
- SoLV: % dos pontos em que o local esta no top 3;
- found: em quantos pontos aparece.
Funcoes puras: entram as posicoes (None = fora dos 20), saem os numeros."""

from ranking.config import NOT_FOUND_RANK, TOP_N


def summary(positions):
    """positions: lista com a posicao em cada ponto avaliado (1..20 ou None)."""
    total = len(positions)
    found = [p for p in positions if p is not None]
    if not total:
        return {"arp": None, "atrp": None, "solv": None, "found": 0, "points": 0}
    return {"arp": round(sum(found) / len(found), 2) if found else None,
            "atrp": round(sum(p if p is not None else NOT_FOUND_RANK for p in positions) / total, 2),
            "solv": round(100 * sum(1 for p in found if p <= TOP_N) / total, 2),
            "found": len(found), "points": total}


def competitors(points):
    """points: lista dos pontos avaliados, cada um com a lista ordenada de resultados (reader.read_point).
    Devolve todos os locais que apareceram em algum ponto, com as metricas de cada um e as posicoes por ponto,
    ordenados por SoLV (maior primeiro) e, no empate, pelo ATRP (menor primeiro)."""
    by_key, order = {}, []
    for idx, results in enumerate(points):
        for n, r in enumerate(results, 1):
            key = r.get("placeId") or r.get("cid")
            if key not in by_key:
                by_key[key] = {"info": r, "positions": [None] * len(points)}
                order.append(key)
            entry = by_key[key]
            if entry["positions"][idx] is None:
                entry["positions"][idx] = n
    out = []
    for key in order:
        e = by_key[key]
        out.append({**{k: e["info"].get(k) for k in ("placeId", "cid", "name", "rating", "reviews", "category",
                                                     "address", "lat", "lng")},
                    "positions": e["positions"], **summary(e["positions"])})
    out.sort(key=lambda c: (-c["solv"], c["atrp"]))
    return out
