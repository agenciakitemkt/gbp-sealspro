"""Adaptador: converte o `pd` (profile_data) de uma pre analise guardada no GBP Check para o perfil normalizado da
Pre Analise, o mesmo formato que o motor (scoring/pre) le e que a coleta futura vai produzir.

Perfil normalizado da Pre (os dias ja vem contados no momento da coleta, como o Google os mostra: "ha 3 meses" = 90):
  {"source", "collectedAt",
   "location": {id, placeId, name, category, categories, city, address, phone, website, description, hours,
                logoUrl, coverUrl, mapsUrl, verified, socialLinks: [{name, url}]},
   "reviews": {count, average, starDistribution (5 -> 1 estrelas), lastReviewDays,
               sample: None | {size, unanswered, withText, average, e ratings (notas da mais recente para a mais
                               antiga; leitor da extensao) ou recentSize e recentAverage (ja calculados pelo original)}},
   "media": None | {lastOwnerPhotoDays, videos, photos360, total},
   "posts": {count, lastPostDays},
   "competitors": None | {count, averageReviews, inTop10ByReviews}}
`None` num grupo = o dado nao foi coletado (os itens que dependem dele ficam fora da nota).
"""

import uuid
from datetime import datetime, timezone

SOURCE = "gbpcheck_original"


def _int(value):
    """reviews_qty vem como numero, None ou "" (sem avaliacoes: a distribuicao por estrelas vem zerada)."""
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _num(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def analyzed_at(case_id):
    """O id da pre analise no original e um UUID v7: os 48 primeiros bits sao o instante da analise, em ms."""
    try:
        ms = uuid.UUID(case_id).int >> 80
    except (ValueError, AttributeError, TypeError):
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def _sample(stats):
    if not stats or not stats.get("total_reviews"):
        return None
    recent = stats.get("last_fixed_statistics") or {}
    return {"size": stats["total_reviews"], "unanswered": stats.get("not_answered", 0),
            "withText": stats.get("reviews_with_text", 0), "average": _num(stats.get("avg_rating")),
            "recentSize": stats.get("last_fixed_n") or recent.get("total_reviews"),
            "recentAverage": _num(recent.get("avg_rating"))}


def _media(stats, total_photos):
    if stats is None:
        return None
    return {"lastOwnerPhotoDays": stats.get("last_media_days_since"), "videos": stats.get("video_count") or 0,
            "photos360": stats.get("image_360_count") or 0,
            "total": total_photos if total_photos is not None else stats.get("total_items")}


def _competitors(pd, count):
    return {"count": count or 0, "averageReviews": _num(pd.get("avg_reviews_count_all")) or 0,
            "inTop10ByReviews": bool(pd.get("is_location_on_top_10"))}


def to_profile(case):
    """`case` = uma entrada de pre_analises_original.json ({id, pd, ncomp, ...}) ou so o `pd`."""
    pd = case.get("pd", case)
    info = pd.get("address_info") or {}
    stars = pd.get("reviews_by_stars") or [0, 0, 0, 0, 0]  # no original: 1 -> 5 estrelas
    count = _int(pd.get("reviews_qty"))
    when = analyzed_at(case.get("id")) if "pd" in case else None
    ncomp = case.get("ncomp", pd.get("competitors_considered_count"))
    return {
        "source": SOURCE,
        "collectedAt": (when or datetime.now(timezone.utc)).isoformat(),
        "location": {
            "id": pd.get("cid") or "", "placeId": pd.get("place_id") or "",
            "name": pd.get("location_name") or "", "category": pd.get("category") or "",
            "categories": pd.get("all_categories") or [], "city": info.get("city") or "",
            "address": pd.get("address") or "", "phone": next(iter(pd.get("phones") or []), ""),
            "website": pd.get("website") or "", "description": pd.get("description") or "",
            "hours": pd.get("hours") or {}, "logoUrl": pd.get("logo_url") or "",
            "coverUrl": pd.get("cover_photo_url") or "",
            "mapsUrl": f"https://maps.google.com/?cid={pd['cid']}" if pd.get("cid") else "",
            "verified": bool(pd.get("is_verified")),
            "socialLinks": [{"name": s.get("name", ""), "url": s.get("url", "")} for s in pd.get("social_links") or []],
        },
        "reviews": {"count": count, "average": _num(pd.get("reviews_average")) if count else None,
                    "starDistribution": list(reversed(stars)), "lastReviewDays": pd.get("last_review_days_ago"),
                    "sample": _sample(pd.get("reviews_statistics"))},
        "media": _media(pd.get("media_statistics"), pd.get("total_photos")),
        "posts": {"count": pd.get("posts_count") or 0, "lastPostDays": pd.get("last_post_days_ago")},
        "competitors": _competitors(pd, ncomp),
    }
