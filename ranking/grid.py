"""Grade de pontos em volta do negocio. Mesma geometria do GBP Check (lida em 2026-10-11), para comparar ponto a ponto:
um quadrado de lado 2 x raio centrado no local, com size x size pontos igualmente espacados. A ordem e linha a linha,
do sul para o norte e, em cada linha, do oeste para o leste; o ponto central e o do meio da lista."""

import math

METERS_PER_DEGREE = 111320


def make_grid(lat, lng, size, radius_m):
    """Lista de {"i", "lat", "lng"} com size*size pontos. size impar >= 1; raio em metros."""
    if size < 1 or size % 2 == 0:
        raise ValueError("a grade precisa ter lado impar")
    if size == 1:
        return [{"i": 0, "lat": lat, "lng": lng}]
    span_lat = 2 * radius_m / METERS_PER_DEGREE
    span_lng = 2 * radius_m / (METERS_PER_DEGREE * math.cos(math.radians(lat)))
    step_lat, step_lng = span_lat / (size - 1), span_lng / (size - 1)
    points = []
    for row in range(size):
        for col in range(size):
            points.append({"i": len(points), "lat": lat - span_lat / 2 + row * step_lat,
                           "lng": lng - span_lng / 2 + col * step_lng})
    return points


def spacing_m(size, radius_m):
    """Distancia entre pontos vizinhos, em metros."""
    return 0 if size < 2 else 2 * radius_m / (size - 1)
