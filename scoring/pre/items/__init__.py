"""Catálogo dos 20 itens da Pré Análise, na ordem do relatório do original."""

from scoring.pre.items import (above_segment_average, business_name, description, hours, last_owner_photo,
                               last_post, last_review, logo, phone, photos_360, reviews_average, reviews_count,
                               reviews_trend, reviews_unanswered, reviews_with_text, social_links, top10_reviews,
                               verified, videos, website)

ITEMS = tuple(m.ITEM for m in (
    business_name, phone, website, hours, description, logo, verified, social_links, last_post, last_owner_photo,
    videos, photos_360, reviews_count, reviews_average, last_review, reviews_trend, reviews_unanswered,
    reviews_with_text, top10_reviews, above_segment_average))
