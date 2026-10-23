"""Catálogo dos 21 itens da Análise Completa, na ordem dos ids do original."""

from scoring.items import (business_name, cover, customer_media, description, founding_date, hours,
                           last_owner_media, last_post, logo, owner_media, phone, reviews_average,
                           reviews_count, reviews_no_comment, reviews_trend, reviews_unanswered,
                           services, special_hours, total_media, videos, website)

ITEMS = sorted((m.ITEM for m in (
    phone, website, hours, special_hours, description, videos, logo, cover, owner_media, total_media,
    customer_media, reviews_count, reviews_average, reviews_unanswered, reviews_no_comment, services,
    founding_date, business_name, reviews_trend, last_post, last_owner_media)), key=lambda i: i.legacy_id)
