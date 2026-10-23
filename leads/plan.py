"""Grade de pontos sobre a regiao da busca e a lista de pedidos que a extensao faz (ponto e pagina)."""

import math

from leads import config
from ranking.grid import METERS_PER_DEGREE


class RegionError(Exception):
    """Mensagem em portugues, para a tela."""


def _m_per_deg_lng(lat):
    return METERS_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01)


def area(region):
    """Retangulo da regiao com o lado minimo garantido. Devolve (south, north, west, east, lado_ns_m, lado_lo_m)."""
    lat, lng = region["lat"], region["lng"]
    south, north, west, east = region["south"], region["north"], region["west"], region["east"]
    min_lat = config.REGION_MIN_HALF_M / METERS_PER_DEGREE
    min_lng = config.REGION_MIN_HALF_M / _m_per_deg_lng(lat)
    south, north = min(south, lat - min_lat), max(north, lat + min_lat)
    west, east = min(west, lng - min_lng), max(east, lng + min_lng)
    ns = (north - south) * METERS_PER_DEGREE
    ew = (east - west) * _m_per_deg_lng((north + south) / 2)
    if max(ns, ew) > config.REGION_MAX_SIDE_M:
        raise RegionError(f"A região é grande demais ({max(ns, ew) / 1000:.0f} km de lado; o máximo é "
                          f"{config.REGION_MAX_SIDE_M // 1000} km). Escolha uma cidade ou um bairro.")
    return south, north, west, east, ns, ew


def make_points(region, size):
    """size x size pontos no centro de cada celula do retangulo, do sul para o norte e do oeste para o leste.
    Devolve (pontos [{i, lat, lng}], distancia de visao em metros)."""
    south, north, west, east, ns, ew = area(region)
    dlat, dlng = (north - south) / size, (east - west) / size
    points = [{"i": r * size + c, "lat": south + dlat * (r + 0.5), "lng": west + dlng * (c + 0.5)}
              for r in range(size) for c in range(size)]
    spacing = max(ns, ew) / size
    view = int(min(max(spacing, config.VIEW_MIN_M), config.VIEW_MAX_M))
    return points, view


def requests_for(points, pages):
    """Pedidos na ordem em que a extensao faz: cada ponto com as suas paginas seguidas. [[lat, lng, inicio], ...]"""
    return [[round(p["lat"], 7), round(p["lng"], 7), page * config.RESULTS_PER_PAGE]
            for p in points for page in range(pages)]


def inside(region, lat, lng):
    """O negocio fica dentro do retangulo da regiao (com uma margem)?"""
    if lat is None or lng is None:
        return None
    south, north, west, east, _, _ = area(region)
    m_lat = config.REGION_MARGIN_M / METERS_PER_DEGREE
    m_lng = config.REGION_MARGIN_M / _m_per_deg_lng(lat)
    return south - m_lat <= lat <= north + m_lat and west - m_lng <= lng <= east + m_lng
