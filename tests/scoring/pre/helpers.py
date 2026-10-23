import copy
from datetime import datetime

NOW = datetime.fromisoformat("2026-07-09T00:00:00+00:00")

_GOOD = {
    "source": "teste",
    "collectedAt": NOW.isoformat(),
    "location": {
        "id": "0000000000000000001", "placeId": "", "name": "Negócio Exemplo", "category": "Oftalmologista",
        "categories": ["Ophthalmologist"], "city": "Cidade Exemplo", "address": "Rua Exemplo, 100",
        "phone": "+55 00 0000-0000", "website": "https://example.com/", "description": "x" * 300,
        "hours": {"Monday": "8 AM–6 PM"}, "logoUrl": "https://example.com/logo.jpg",
        "coverUrl": "https://example.com/capa.jpg", "mapsUrl": "", "verified": True,
        "socialLinks": [{"name": "Instagram", "url": "https://www.instagram.com/exemplo/"}],
    },
    "reviews": {"count": 40, "average": 4.9, "starDistribution": [38, 2, 0, 0, 0], "lastReviewDays": 7,
                "sample": {"size": 40, "unanswered": 0, "withText": 36, "average": 4.9, "recentSize": 5,
                           "recentAverage": 5.0}},
    "media": {"lastOwnerPhotoDays": 7, "videos": 3, "photos360": 2, "total": 30},
    "posts": {"count": 4, "lastPostDays": 3},
    "competitors": {"count": 80, "averageReviews": 30, "inTop10ByReviews": True},
}


def profile(**changes):
    """Perfil normalizado da Pre com os 20 itens em 100. `changes`: caminho com '__' -> valor
    (ex.: reviews__sample__unanswered=3)."""
    p = copy.deepcopy(_GOOD)
    for path, value in changes.items():
        *parents, key = path.split("__")
        node = p
        for k in parents:
            node = node[k]
        node[key] = value
    return p


def run(item, p):
    return item.evaluate(p, NOW)


def score(item, **changes):
    return run(item, profile(**changes)).score
