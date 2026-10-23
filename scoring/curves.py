"""Curvas de nota. Funcoes puras; os pontos vem de scoring.config."""

import math


def to_score(raw, reached_good):
    """Trunca para inteiro; so chega a 100 quando o caso bom foi atingido (nunca 100 por arredondamento)."""
    if reached_good:
        return 100
    return max(0, min(99, math.floor(raw + 1e-9)))


def interpolate(x, knots):
    """Interpolacao linear por partes; fora dos extremos usa o valor do extremo mais proximo."""
    pts = sorted(knots)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def count_score(value, recommended, measured=None):
    knots = [(0, 0), *(measured or {}).items(), (recommended, 100)]
    return to_score(interpolate(value, knots), value >= recommended)


def step_score(value, steps, beyond):
    """Curva em degraus: a primeira faixa `(limite_inclusivo, nota)` que contem o valor; depois da ultima, `beyond`."""
    for limit, score in steps:
        if value <= limit:
            return score
    return beyond
