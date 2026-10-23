"""Leitor da captura do Google Maps feita pela extensao propria (CLAUDE.md, secao 13): transforma os dados brutos no
perfil normalizado da Pre Analise (formato em collector_pre/from_original.py).

Captura (o que a extensao envia, sem interpretar nada):
  {"capturedAt": ISO 8601,
   "place":   resposta de /maps/preview/place (texto com ")]}'" ou JSON ja lido)         fonte A
   "reviews": [paginas de batchexecute rpcids=qv9Egd, "Mais recentes"]                      fonte B
   "reviewsLowest": [paginas qv9Egd ordenadas por "Menor classificacao"]                      fonte B (0.4.3)
   "reviewsSearch": {"lowest": [...], "newest": [...]} paginas GetLocalBoqProxy da busca     fonte B' (0.4.4)
   "photos":  [paginas de batchexecute rpcids=hspqX, galeria "Mais recentes"]               fonte C
   "photosOwner":  [paginas hspqX da categoria "Do proprietario" da galeria]               fonte C (fase 2)
   "photosVideos": [paginas hspqX da categoria "Videos" da galeria]                         fonte C (fase 2)
   "photos360":    [paginas hspqX da categoria "Street View e 360°" da galeria]             fonte C (0.4.1)
   "search":  [paginas da busca tbm=map, resultados em [64]]                                fonte D
   "socialLinks": [links do bloco "Perfis" do painel da busca do Google]}                   fonte E (parte)
Fonte ausente (None) = nao coletada. socialLinks so vem quando a captura comeca pelo botao na busca do Google.

Regra geral: "nao avaliado" so quando a fonte nao foi coletada (ou o formato nao e o esperado). Fonte coletada e dado
inexistente vale 0, como no original. Os itens nao avaliados vao em `notCollected` (ids de item do motor) e cada
formato inesperado gera um aviso em `warnings` ("leitor desatualizado"). O leitor nunca levanta excecao por causa do
conteudo da captura.

Da fonte E so as redes sociais (bloco "Perfis"); as postagens vem da fonte A.
As posicoes foram mapeadas em 2026-10-09 (data/reference/maps/mapa_campos.py).
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from scoring.pre.config import CONFIG

SOURCE = "extensao"
PREFIX = ")]}'"
# Categorias da galeria na fonte A ([6][171][0][i] = [codigo, ?, nome, ...]). O codigo se repetiu nos 9 perfis
# mapeados e na primeira captura real; o nome depende do idioma do Maps. Vale o codigo; o nome (pt e en) e reserva.
OWNER_CODES, OWNER_NAMES = {"CgIgARICEAE="}, {"do proprietário", "from the owner", "by owner"}
VIDEO_CODES, VIDEO_NAMES = {"CgIgARICCAQ="}, {"vídeos", "videos"}
PANO_CODES, PANO_NAMES = {"CgIgARICCAI="}, {"street view e 360°", "street view & 360°", "street view and 360°"}
PHOTOS_PER_PAGE = 20
SOCIAL_FIELDS = ("social_links",)   # so no painel da busca do Google (bloco "Perfis"), lido no clique do botao
# Nome de cada rede pelo dominio (sem www.). Dominio fora da lista: vale o proprio dominio como nome.
SOCIAL_NAMES = {"instagram.com": "Instagram", "facebook.com": "Facebook", "linkedin.com": "LinkedIn",
                "youtube.com": "YouTube", "tiktok.com": "TikTok", "x.com": "X", "twitter.com": "X",
                "pinterest.com": "Pinterest", "threads.net": "Threads", "threads.com": "Threads"}
MAX_SOCIAL = 10
# Amostra de avaliacoes: as 100 mais recentes, como manda a spec (13.3). O GBP Check le todas ate cerca de 130 e, acima
# disso, de 38 a 91 das mais recentes; a extensao chegou a mandar 230 (o limite de paginas nao valia), o que mudava os
# percentuais de sem resposta e com comentario (comparacao ao vivo, 2026-10-10).
SAMPLE_MAX = 100
# Amostra da busca (como o GBP Check): com ate SEARCH_FULL_MAX avaliacoes no perfil, todas; acima, as 5 primeiras paginas
# (50) de cada lista. Medido: 129 de 129, 115 de 115 e 64 de 64 lidas inteiras; com 250 ou mais, 5 + 5 paginas. O corte
# exato fica entre 130 e 249 (hipotese: 130, o que a extensao alcanca nas mais recentes).
SEARCH_PAGE_SIZE, SEARCH_PAGES, SEARCH_FULL_MAX = 10, 5, 130
NO_SOURCE = ()                                   # itens sem fonte (o 360 ganhou a dele na 0.4.1)
PLACE_ITEMS = ("business_name", "phone", "website", "hours", "description", "logo", "verified", "reviews_count", "last_post",
               "reviews_average", "last_review", "last_owner_photo", "videos", "top10_reviews",
               "above_segment_average")


def g(o, *path):
    """Acesso seguro: devolve None em vez de quebrar quando a posicao nao existe."""
    for k in path:
        try:
            o = o[k]
        except (IndexError, KeyError, TypeError):
            return None
    return o


class Reading:
    """Acumula o que nao foi avaliado e os avisos de formato durante a leitura."""

    def __init__(self):
        self.not_collected, self.warnings = [], []

    def skip(self, *items):
        for item in items:
            if item not in self.not_collected:
                self.not_collected.append(item)

    def warn(self, text, *items):
        if text not in self.warnings:
            self.warnings.append(text)
        self.skip(*items)


def _json(raw):
    """Texto com ou sem o prefixo )]}' (e o sufixo /*""*/ da busca) -> JSON; JSON ja lido passa direto.
    A busca do Maps pode vir embrulhada em {"d": "<texto>"}: o texto de "d" e lido do mesmo jeito. None se ilegivel."""
    if isinstance(raw, dict) and isinstance(raw.get("d"), str):
        return _json(raw["d"])
    if raw is None or isinstance(raw, (list, dict)):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.endswith('/*""*/'):
        text = text[:-len('/*""*/')].rstrip()
    if text.startswith(PREFIX):
        text = text[len(PREFIX):]
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return _json(data) if isinstance(data, dict) and isinstance(data.get("d"), str) else data


def batchexecute(text):
    """Resposta de batchexecute (formato wrb.fr): o JSON interno do primeiro bloco. None se nao der para ler."""
    if not isinstance(text, str):
        return None
    for line in text.split("\n"):
        if '"wrb.fr"' not in line:
            continue
        try:
            inner = g(json.loads(line), 0, 2)
            return json.loads(inner) if isinstance(inner, str) else None
        except ValueError:
            return None
    return None


def cid_from_ftid(ftid):
    """'0x...:0x7c35...' -> CID decimal (parte depois de ':' em hexadecimal)."""
    if not isinstance(ftid, str) or ":" not in ftid:
        return None
    try:
        return str(int(ftid.split(":", 1)[1], 16))
    except ValueError:
        return None


def _is(value, *types):
    return value is None or (isinstance(value, types) and not isinstance(value, bool))


def _days(now, when):
    return max(0, (now - when).days)


def as_google_days(days):
    """Dias exatos -> dias na escala do GBP Check, que le o texto do Google ("ha 2 meses") e converte (2 x 30). Os cortes
    das regras foram calibrados nessa escala, entao a nota usa ela. Conferido em 2026-10-10: 169 dias = "5 meses" = 150
    (ultima avaliacao), 65 = "2 meses" = 60 (ultima foto do dono), 806 = "2 anos" = 730.
    Semanas (7 a 29 dias) sao hipotese: "ha 2 semanas" = 14."""
    if days is None or days < 7:
        return days
    if days < 30:
        return days // 7 * 7
    if days < 365:
        return days // 30 * 30
    return days // 365 * 365


def _from_us(us):
    return datetime.fromtimestamp(us / 1e6, timezone.utc)


# ---------------------------------------------------------------------------
# Fonte A: dados do local
# ---------------------------------------------------------------------------

def _posts(p, now, reading):
    """Postagens do proprietario na fonte A, [122][1]: lista; em cada uma, [2][0] = criacao em segundos Unix.
    Conferido em 2026-10-10 em perfis de terceiros (datas iguais as da tela) e nos do usuario.
    Sem [122] (ou lista vazia) = nao tem postagem (vale 0, como no original)."""
    block = g(p, 122)
    posts = g(block, 1)
    if block is None or posts is None:
        return {"count": 0, "lastPostDays": None}
    if not isinstance(posts, list):
        reading.warn("Leitor desatualizado: postagens em formato inesperado (fonte A).", "last_post")
        return {"count": 0, "lastPostDays": None}
    stamps = [g(x, 2, 0) for x in posts]
    stamps = [t for t in stamps if isinstance(t, int) and not isinstance(t, bool) and 10 ** 9 < t < 10 ** 10]
    if posts and not stamps:
        reading.warn("Leitor desatualizado: postagens sem data no formato esperado (fonte A).", "last_post")
        return {"count": len(posts), "lastPostDays": None}
    last = max(stamps) if stamps else None
    return {"count": len(posts),
            "lastPostDays": as_google_days(_days(now, datetime.fromtimestamp(last, timezone.utc))) if last else None}


def read_place(raw, reading, expected_ftid=None, now=None):
    """Devolve (location, reviews_count, reviews_average, stars_5_a_1, gallery_categories, posts) ou None se ilegivel
    ou se for de outro local (o Maps tambem busca dados de outros locais do mapa)."""
    payload = _json(raw)
    p = g(payload, 6)
    if not isinstance(p, list) or not isinstance(g(p, 11), str):
        reading.warn("Leitor desatualizado: não foi possível ler os dados do local (fonte A).", *PLACE_ITEMS)
        return None
    if expected_ftid and g(p, 10) != expected_ftid:
        reading.warn(f"A captura trouxe os dados de outro local do mapa ({p[11][:60]}), e não do perfil aberto: "
                     "itens do perfil não avaliados. Rode de novo.", *PLACE_ITEMS)
        return None

    def field(path, types, item, label):
        value = g(p, *path)
        if not _is(value, *types):
            reading.warn(f"Leitor desatualizado: {label} em formato inesperado (fonte A).", item)
            return None
        return value

    phone = field((178, 0, 0), (str,), "phone", "telefone")
    site = field((7, 0), (str,), "website", "site")
    description = field((154, 0, 0), (str,), "description", "descrição")
    logo = field((157,), (str,), "logo", "logotipo")
    hours_raw = field((203, 0), (list,), "hours", "horário")
    rating = field((4, 7), (int, float), "reviews_average", "nota média")
    count = field((4, 8), (int,), "reviews_count", "total de avaliações")
    if count is None and g(p, 4, 8) is not None:  # formato errado: a contagem decide outros itens
        reading.skip("reviews_average", "last_review", "above_segment_average", "top10_reviews")
    stars = g(p, 175, 3)
    stars = list(reversed(stars)) if isinstance(stars, list) and len(stars) == 5 else [0, 0, 0, 0, 0]
    categories = [(c[0] if isinstance(c[0], str) else "", c[2].strip().lower())
                  for c in (g(p, 171, 0) or []) if isinstance(g(c, 2), str)]
    hours = {}
    for day in hours_raw or []:
        if isinstance(g(day, 0), str):
            hours[day[0]] = [h[0] for h in (g(day, 3) or []) if isinstance(g(h, 0), str)]
    cid = cid_from_ftid(g(p, 10))
    location = {
        "id": cid or "", "placeId": g(p, 78) if isinstance(g(p, 78), str) else "",
        "name": p[11], "category": g(p, 13, 0) if isinstance(g(p, 13, 0), str) else "",
        "categories": [c for c in (g(p, 13) or []) if isinstance(c, str)],
        "city": "", "address": g(p, 39) if isinstance(g(p, 39), str) else "",
        "lat": g(p, 9, 2), "lng": g(p, 9, 3),
        "phone": phone or "", "website": site or "", "description": description or "", "hours": hours,
        "logoUrl": logo or "", "coverUrl": "",
        "mapsUrl": f"https://maps.google.com/?cid={cid}" if cid else "",
        # Link "reivindicar esta empresa" presente em [49] = nao verificado
        "verified": g(p, 49) is None,
        "socialLinks": [],
    }
    return location, count or 0, rating, stars, categories, _posts(p, now or datetime.now(timezone.utc), reading)


# ---------------------------------------------------------------------------
# Fonte B: avaliacoes ("Mais recentes")
# ---------------------------------------------------------------------------

def read_reviews(pages, reading):
    """Lista de avaliacoes [{at, rating, hasText, replied}] na ordem da captura, ou None se ilegivel."""
    out = []
    for page in pages:
        inner = batchexecute(page)
        items = g(inner, 2)
        if inner is None or not _is(items, list):
            reading.warn("Leitor desatualizado: página de avaliações em formato inesperado (fonte B).")
            return None
        for item in items or []:
            r = g(item, 0)
            us = g(r, 1, 3) or g(r, 1, 2)  # [1][3] = ultima edicao (a data que o Google mostra); [1][2] = criacao
            rating = g(r, 2, 0, 0)
            if not isinstance(us, int) or not isinstance(rating, int):
                reading.warn("Leitor desatualizado: avaliação sem data ou nota no formato esperado (fonte B).")
                continue
            out.append({"at": _from_us(us), "rating": rating, "hasText": bool(g(r, 2, 15, 0, 0)),
                        "replied": bool(g(r, 3, 1) or g(r, 3, 14))})
    return out


def read_search_reviews(obj, reading, total=None):
    """Amostra como a do GBP Check: caixa de avaliacoes da busca do Google (GetLocalBoqProxy, hl=en-BR), lista "menor
    nota" + lista "mais recentes", ate 5 paginas cada, sem repetir (pelo id da avaliacao). Conferido em 2026-10-10 em
    Em 3 perfis de terceiros: tamanho, media, com comentario e sem resposta iguais aos do GBP Check.
    Avaliacao `rv`: nota em rv[1], data em rv[2][2] (milissegundos, texto), resposta do dono em rv[4], id em rv[5] e
    texto em rv[27]. Devolve [{at, rating, hasText, replied}] ou None se ilegivel."""
    if not isinstance(obj, dict) or not all(isinstance(obj.get(k), list) for k in ("lowest", "newest")):
        reading.warn("Leitor desatualizado: amostra de avaliações da busca em formato inesperado.")
        return None
    out, seen = [], set()
    full = isinstance(total, int) and total <= SEARCH_FULL_MAX
    pages = obj["lowest"] if full else obj["lowest"][:SEARCH_PAGES]
    pages = pages + (obj["newest"] if full else obj["newest"][:SEARCH_PAGES])
    for text in pages:
        data = _json(text) if isinstance(text, str) else None
        reviews = g(data, 1, 10, 2)
        if not isinstance(reviews, list):
            reading.warn("Leitor desatualizado: página de avaliações da busca em formato inesperado.")
            return None
        for rv in reviews:
            rid, rating, ms = g(rv, 5), g(rv, 1), g(rv, 2, 2)
            try:
                when = datetime.fromtimestamp(int(ms) / 1000, timezone.utc)
            except (TypeError, ValueError, OverflowError, OSError):
                when = None
            if not isinstance(rid, str) or not isinstance(rating, int) or not 1 <= rating <= 5 or when is None:
                reading.warn("Leitor desatualizado: avaliação da busca sem nota, data ou id no formato esperado.")
                return None
            if rid in seen:
                continue
            seen.add(rid)
            text_ = g(rv, 27)
            out.append({"at": when, "rating": rating, "hasText": isinstance(text_, str) and bool(text_.strip()),
                        "replied": g(rv, 4) is not None})
    return out


def _sample(reviews):
    """A amostra como veio, da mais recente para a mais antiga. Quantas entram na tendencia (N) e regra de nota:
    fica no motor (scoring/pre/config.py, reviews_trend)."""
    return {"size": len(reviews), "unanswered": sum(not r["replied"] for r in reviews),
            "withText": sum(r["hasText"] for r in reviews),
            "average": round(sum(r["rating"] for r in reviews) / len(reviews), 2),
            "ratings": [r["rating"] for r in reviews]}


# ---------------------------------------------------------------------------
# Fonte C: galeria de fotos ("Mais recentes")
# ---------------------------------------------------------------------------

def _photo_list(inner):
    """Lista de itens da galeria: a primeira lista cujos itens comecam com um id de foto."""
    for x in inner if isinstance(inner, list) else []:
        if isinstance(x, list) and x and all(isinstance(it, list) and isinstance(g(it, 0), str) for it in x):
            return x
    return [] if isinstance(inner, list) else None


def _strings(o):
    if isinstance(o, list):
        for x in o:
            yield from _strings(x)
    elif isinstance(o, str):
        yield o


def read_photos(pages, reading, codes=None):
    """(itens [{date, owner, video, sphere}], galeria lida ate o fim) ou None se ilegivel.
    codes: categoria pedida (aba controlada). Cada pagina da galeria diz a sua categoria em [13][0]; so valem as da
    categoria pedida. As outras ficam de fora: a de outro bloco clicado na reserva e a do visualizador do Street View,
    que o Maps abre sozinho na categoria 360 e que busca panoramas vizinhos pelo mesmo hspqX, sem [13] (achado em
    2026-10-10: 4 panoramas vizinhos no lugar dos 2 itens da categoria).
    sphere: foto esferica (360), marcada com 2 em [21][2][1] (fotos comuns: 3 ou 4), tanto no panorama do Street View
    (origem "launch") quanto na foto esferica enviada por alguem (conferido em 2 perfis, 2026-10-10).
    Fim da galeria (hipotese conferida em 1 galeria): a ultima pagina traz True em [10] ou menos de 20 itens."""
    out, complete, kept = [], False, 0
    for page in pages:
        inner = batchexecute(page)
        if codes and g(inner, 13, 0) not in codes:
            continue
        kept += 1
        items = _photo_list(inner)
        if items is None:
            reading.warn("Leitor desatualizado: página da galeria em formato inesperado (fonte C).")
            return None
        for it in items:
            strings = list(_strings(it))
            date = g(it, 21, 6, 8)
            when = None
            if isinstance(date, list) and len(date) >= 3 and all(isinstance(v, int) for v in date[:3]):
                try:
                    when = datetime(date[0], date[1], date[2], tzinfo=timezone.utc)
                except ValueError:
                    when = None
            out.append({"date": when, "owner": any(s.startswith("bizbuilder:") for s in strings),
                        "video": any("=mm,hls" in s or "=mm,dash" in s for s in strings),
                        "sphere": g(it, 21, 2, 1) == 2})
        complete = g(inner, 10) is True or len(items) < PHOTOS_PER_PAGE
    if codes and pages and not kept:
        reading.warn("Nenhuma página veio da categoria pedida da galeria (fonte C).")
        return None
    if any(p["owner"] and p["date"] is None for p in out):
        reading.warn("Leitor desatualizado: foto do proprietário sem data no formato esperado (fonte C).")
    return out, complete


def _media(now, categories, galleries, reading):
    """Ultima foto do proprietario e videos, cruzando a fonte A (categorias da galeria) com a fonte C.

    `galleries`: {"recent", "owner", "videos", "pano"} -> (itens, lida ate o fim) ou None (nao capturada). As categorias
    "Do proprietario" e "Videos" (fase 2 da extensao) tem prioridade sobre a "Mais recentes": lidas inteiras, nao
    dependem da ordem da galeria. Na categoria "Do proprietario" todo item conta como do proprietario."""
    has = lambda codes, names: any(code in codes or name in names for code, name in categories)  # noqa: E731
    has_owner, has_videos = has(OWNER_CODES, OWNER_NAMES), has(VIDEO_CODES, VIDEO_NAMES)
    has_pano = has(PANO_CODES, PANO_NAMES)
    media = {"lastOwnerPhotoDays": None, "videos": 0, "photos360": None, "total": None}

    # Ultima foto do proprietario: sem a categoria "Do proprietario" na fonte A = nao tem (vale 0).
    if has_owner:
        owner_category = galleries.get("owner") is not None
        source = galleries.get("owner") if owner_category else galleries.get("recent")
        if source is None:
            reading.skip("last_owner_photo")
        else:
            items, complete = source
            dates = [p["date"] for p in items if (p["owner"] or owner_category) and p["date"]]
            best = as_google_days(_days(now, max(dates))) if dates else None
            good_limit = CONFIG["last_owner_photo"]["steps"][0][0]
            if complete or (best is not None and best <= good_limit):
                media["lastOwnerPhotoDays"] = best  # galeria fora de ordem: so e final lida inteira ou ja no melhor
                if best is None:
                    reading.warn("A fonte A indica fotos do proprietário, mas nenhuma apareceu na galeria lida inteira.")
            else:
                reading.warn("A galeria não foi lida até o fim e a foto do proprietário mais recente pode não ter "
                             "aparecido: última foto do proprietário não avaliada.", "last_owner_photo")

    # Videos: sem a categoria "Videos" na fonte A = 0. Com 3 ou mais encontrados, resolvido; lida inteira, final.
    if has_videos:
        source = galleries.get("videos") if galleries.get("videos") is not None else galleries.get("recent")
        if source is None:
            reading.skip("videos")
        else:
            items, complete = source
            found = sum(p["video"] for p in items)
            if found >= CONFIG["videos"]["recommended"] or complete:
                media["videos"] = found
            else:
                reading.warn(f"A galeria não foi lida até o fim e só {found} vídeos apareceram: vídeos não avaliados.",
                             "videos")

    # Fotos 360: itens esfericos da categoria "Street View e 360°", contando o panorama do Street View, como o original
    # (1 = so o Street View = 0; 2 ou mais = 100). Sem a categoria na fonte A = 0. So a categoria conta: a "Mais
    # recentes" nao traz todas.
    media["photos360"] = 0
    if has_pano:
        source = galleries.get("pano")
        if source is None:
            reading.skip("photos_360")
        else:
            items, complete = source
            found = sum(p["sphere"] for p in items)
            if items and not found:
                reading.warn("Leitor desatualizado: nenhum item da categoria 360° com a marca de foto esférica "
                             "(fonte C).", "photos_360")
            elif found >= CONFIG["photos_360"]["min_count"] or complete:
                media["photos360"] = found
            else:
                reading.warn(f"A categoria 360° não foi lida até o fim e só {found} apareceram: fotos 360° não "
                             "avaliadas.", "photos_360")
    return media


# ---------------------------------------------------------------------------
# Fonte D: concorrentes (busca tbm=map)
# ---------------------------------------------------------------------------

# Concorrentes "do segmento": o GBP Check filtra a busca por categorias parecidas com as do negocio (num caso de
# oftalmologista: ficam Oftalmologista, Clinica oftalmologica e Oftalmologista pediatrico; saem Medico, Otica e Hospital).
# O criterio exato dele nao e conhecido. Aproximacao (hipotese, 2026-10-10): a categoria principal do concorrente
# divide um radical (6 primeiras letras, sem acento) de uma palavra nao generica com alguma categoria do negocio. Nos 6
# perfis da comparacao ao vivo, os itens "top 10" e "acima da media" saem iguais aos do GBP Check.
GENERIC_WORDS = {"loja", "de", "da", "do", "das", "dos", "e", "para", "clinica", "centro", "servico", "servicos",
                 "fornecedor", "prestador", "empresa", "consultorio", "especializada", "especializado", "comercial",
                 "atacadista", "agente"}


def _stems(categories):
    out = set()
    for c in categories:
        text = unicodedata.normalize("NFKD", c if isinstance(c, str) else "").encode("ascii", "ignore").decode().lower()
        out.update(w[:6] for w in re.findall(r"[a-z]+", text) if len(w) >= 4 and w not in GENERIC_WORDS)
    return out


def read_search(pages, own_cid, reading, own_categories=None):
    """Lista de quantidades de avaliacoes dos concorrentes (sem anuncios, sem o proprio negocio e, com as categorias do
    negocio, so os de categoria parecida), ou None."""
    related = _stems(own_categories or [])
    counts, seen, readable = [], set(), 0
    for page in pages:
        results = g(_json(page), 64)
        if not isinstance(results, list):
            # pagina ilegivel: pula so ela (as outras continuam valendo); sem nenhuma legivel, nao avalia
            reading.warn("Leitor desatualizado: resultados da busca de concorrentes em formato inesperado (fonte D).")
            continue
        readable += 1
        for e in results:
            p = g(e, 1)
            if not isinstance(p, list) or (isinstance(e, list) and len(e) == 6):
                continue  # anuncio: so 6 posicoes
            cid = cid_from_ftid(g(p, 10))
            if (cid and cid == own_cid) or (cid and cid in seen):
                continue
            seen.add(cid)
            if related and not (_stems((g(p, 13) or [None])[:1]) & related):
                continue  # outro segmento
            n = g(p, 4, 8)
            counts.append(n if isinstance(n, int) and not isinstance(n, bool) else 0)
    return counts if readable else None


def _competitors(counts, own_count):
    if counts is None:
        return None
    if not counts:
        return {"count": 0, "averageReviews": 0, "inTop10ByReviews": False}
    above = sum(1 for n in counts if n > own_count)
    return {"count": len(counts), "averageReviews": round(sum(counts) / len(counts), 1),
            "inTop10ByReviews": above < 10}


# ---------------------------------------------------------------------------
# Captura completa -> perfil normalizado
# ---------------------------------------------------------------------------

def _captured_at(capture, reading):
    try:
        when = datetime.fromisoformat(capture["capturedAt"])
        return when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        reading.warn("Captura sem data válida (capturedAt): usada a hora atual.")
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fonte E (parte): redes sociais do bloco "Perfis" do painel da busca do Google
# ---------------------------------------------------------------------------

def _social_target(href):
    """Endereco da rede: desfaz o redirecionamento do Google (/url?q=...). Nao http(s): None."""
    parts = urlsplit(href)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    if (host == "google.com" or host.startswith("google.") or ".google." in host) and parts.path == "/url":
        target = (parse_qs(parts.query).get("q") or parse_qs(parts.query).get("url") or [""])[0]
        return _social_target(target) if target else None
    return href


def read_social(links, reading):
    """Lista de links (texto) -> [{name, url}]. Lista vazia = o painel nao tinha o bloco (0 redes). None se ilegivel."""
    if not isinstance(links, list) or not all(isinstance(h, str) for h in links):
        reading.warn("Leitor desatualizado: redes sociais em formato inesperado (busca do Google).", *SOCIAL_FIELDS)
        return None
    out, seen = [], set()
    for href in links:
        url = _social_target(href.strip())
        if not url or url in seen:
            continue
        seen.add(url)
        host = urlsplit(url).hostname.lower()
        host = host[4:] if host.startswith("www.") else host
        name = next((n for d, n in SOCIAL_NAMES.items() if host == d or host.endswith("." + d)), host)
        out.append({"name": name, "url": url})
        if len(out) == MAX_SOCIAL:
            break
    return out


def read_capture(capture):
    """Captura da extensao -> perfil normalizado da Pre (com `notCollected` e `warnings`)."""
    reading = Reading()
    capture = capture if isinstance(capture, dict) else {}
    now = _captured_at(capture, reading)
    reading.skip(*NO_SOURCE)
    social = None
    if capture.get("socialLinks") is None:
        reading.skip(*SOCIAL_FIELDS)  # a captura nao comecou pela busca do Google
    else:
        social = read_social(capture["socialLinks"], reading)

    expected = capture.get("profileFtid") if isinstance(capture.get("profileFtid"), str) else None
    place = read_place(capture.get("place"), reading, expected, now) if capture.get("place") is not None else None
    if capture.get("place") is None:
        reading.skip(*PLACE_ITEMS)
    location, count, rating, stars, categories, posts = place or (
        {"id": "", "name": "", "verified": False, "socialLinks": []}, 0, None, [0, 0, 0, 0, 0], [],
        {"count": 0, "lastPostDays": None})
    if place is not None and social is not None:
        location["socialLinks"] = social
    elif place is None and social is not None:
        reading.skip(*SOCIAL_FIELDS)  # sem os dados do local, as redes nao tem a quem pertencer

    # Fonte B. A quantidade de avaliacoes vem sempre da fonte A, nunca do tamanho da amostra.
    # "reviews" (Mais recentes) da a ultima avaliacao. A amostra de sem resposta, com comentario e tendencia vem de
    # "reviewsLowest" (Menor classificacao), como no GBP Check (comparacao ao vivo, 2026-10-10), ordenada por data
    # para a tendencia. Captura sem "reviewsLowest" (anterior a 0.4.3): a amostra sai das mais recentes, como antes.
    sample, last_review_days = None, None
    reviews = read_reviews(capture["reviews"], reading) if capture.get("reviews") is not None else None
    has_lowest = "reviewsLowest" in capture
    search = (read_search_reviews(capture["reviewsSearch"], reading, count if place is not None else None)
              if capture.get("reviewsSearch") is not None else None)
    lowest = read_reviews(capture["reviewsLowest"], reading) if capture.get("reviewsLowest") is not None else None
    if place is not None and count:
        recent_ok = False
        if reviews is None:
            reading.skip("last_review")
        elif not reviews:
            reading.warn("A fonte A indica avaliações, mas nenhuma veio na fonte B.", "last_review")
        else:
            dates = [r["at"] for r in reviews]
            recent_ok = not any(a < b for a, b in zip(dates, dates[1:]))
            if recent_ok:
                last_review_days = as_google_days(_days(now, dates[0]))
            elif has_lowest:
                reading.warn("As avaliações não vieram da mais recente para a mais antiga: última avaliação não "
                             "avaliada.", "last_review")
            else:
                reading.warn("As avaliações não vieram da mais recente para a mais antiga: última avaliação e "
                             "tendência não avaliadas.", "last_review", "reviews_trend")
        if search:  # a amostra do GBP Check tem prioridade; ordenada por data para a tendencia
            sample = _sample(sorted(search, key=lambda r: r["at"], reverse=True))
        elif not has_lowest:
            if reviews:
                sample = _sample(reviews[:SAMPLE_MAX])
        elif lowest:
            sample = _sample(sorted(lowest[:SAMPLE_MAX], key=lambda r: r["at"], reverse=True))
        elif capture.get("reviewsLowest") is not None:
            reading.warn("A fonte A indica avaliações, mas a amostra de menor nota veio vazia: sem resposta, com "
                         "comentário e tendência não avaliados.")

    media = None
    if place is not None:
        # Codigo de cada categoria: o conhecido e o que a fonte A trouxe para o mesmo nome (se o Google trocar o codigo)
        def codes_for(known, names):
            return known | {code for code, name in categories if name in names and code}
        galleries = {name: read_photos(capture[key], reading, codes) if capture.get(key) is not None else None
                     for name, key, codes in (("recent", "photos", None),
                                              ("owner", "photosOwner", codes_for(OWNER_CODES, OWNER_NAMES)),
                                              ("videos", "photosVideos", codes_for(VIDEO_CODES, VIDEO_NAMES)),
                                              ("pano", "photos360", codes_for(PANO_CODES, PANO_NAMES)))}
        media = _media(now, categories, galleries, reading)

    competitors = None
    if place is not None and capture.get("search") is not None:
        competitors = _competitors(read_search(capture["search"], location["id"], reading,
                                               location.get("categories")), count)

    return {
        "source": SOURCE,
        "collectedAt": now.isoformat(),
        "location": location,
        "reviews": {"count": count, "average": rating if count else None, "starDistribution": stars,
                    "lastReviewDays": last_review_days, "sample": sample},
        "media": media,
        "posts": posts,
        "competitors": competitors,
        "notCollected": reading.not_collected,
        "warnings": reading.warnings,
    }
