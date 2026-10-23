"""O que mudou em cada item entre dois brutos da Completa (antes e depois), para o PDF comparativo.

Um item pode continuar na mesma faixa e ainda assim ter sido trabalhado: a descricao reescrita, o logotipo trocado,
fotos novas num perfil que ja tinha muitas. Aqui sai, por item, uma frase curta do que mudou para melhor, ou nada.
So mudancas positivas contam (perder fotos ou a nota cair nao viram "melhoria"); a faixa que piorou continua sendo
decidida pelo status, em build_compare.

Regras: so contagens, datas e tamanhos; nunca texto de avaliacoes de clientes; nunca como a mudanca foi feita.
Fica fora de scoring/: nao muda nota nenhuma.
"""

from datetime import datetime

from report.build import _day


def _pl(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _media_key(m):
    """Identidade de uma midia: o nome que a API da (estavel); sem ele, formato, categoria, data e endereco."""
    return m.get("name") or (m.get("mediaFormat"), (m.get("locationAssociation") or {}).get("category"),
                             m.get("createTime"), m.get("googleUrl") or m.get("sourceUrl"))


def _review_key(r):
    return r.get("reviewId") or r.get("name") or (r.get("createTime"), r.get("starRating"))


def _post_key(p):
    return p.get("name") or (p.get("createTime"), p.get("topicType"))


def _new(before, after, key):
    known = {key(x) for x in before}
    return [x for x in after if key(x) not in known]


def _info(raw):
    return raw.get("info") or {}


def _set(a, b, created, updated):
    """Campo simples: incluido (antes vazio) ou atualizado (diferente). Retirar nao conta como melhoria."""
    if a == b or not b:
        return None
    return created if not a else updated


def _latest(items):
    dates = [x["createTime"] for x in items if x.get("createTime")]
    return _day(max(dates)) if dates else None


def _year_ok(m):
    try:
        return datetime.fromisoformat(m["createTime"].replace("Z", "+00:00")).year > 1970
    except (KeyError, ValueError, AttributeError):
        return False


def _replied(r):
    return bool((r.get("reviewReply") or {}).get("comment"))


def _rating(reviews):
    stars = {"FIVE": 5, "FOUR": 4, "THREE": 3, "TWO": 2, "ONE": 1}
    vals = [stars[r["starRating"]] for r in reviews if r.get("starRating") in stars]
    return round(sum(vals) / len(vals), 1) if vals else None


def _no_comment_pct(reviews):
    if not reviews:
        return None
    return round(100 * sum(1 for r in reviews if not (r.get("comment") or "").strip()) / len(reviews))


def _num(x):
    return f"{x:.1f}".replace(".", ",")


def item_changes(raw_before, raw_after):
    """{id do item: frase do que melhorou}. So aparecem itens com alguma mudanca positiva."""
    ia, ib = _info(raw_before), _info(raw_after)
    out = {}

    def put(item_id, text):
        if text:
            out[item_id] = text

    put("business_name", _set(ia.get("title"), ib.get("title"),
                              "O nome do negócio foi incluído.", "O nome do negócio foi ajustado."))
    put("phone", _set((ia.get("phoneNumbers") or {}).get("primaryPhone"),
                      (ib.get("phoneNumbers") or {}).get("primaryPhone"),
                      "O telefone foi incluído.", "O telefone foi atualizado."))
    put("website", _set(ia.get("websiteUri"), ib.get("websiteUri"),
                        "O site foi incluído no perfil.", "O endereço do site foi atualizado."))
    put("hours", _set((ia.get("regularHours") or {}).get("periods"),
                      (ib.get("regularHours") or {}).get("periods"),
                      "O horário de funcionamento foi incluído.", "O horário de funcionamento foi atualizado."))
    put("special_hours", _set((ia.get("specialHours") or {}).get("specialHourPeriods"),
                              (ib.get("specialHours") or {}).get("specialHourPeriods"),
                              "Os horários de feriados e datas especiais foram incluídos.",
                              "Os horários de feriados e datas especiais foram atualizados."))
    put("founding_date", _set((ia.get("openInfo") or {}).get("openingDate"),
                              (ib.get("openInfo") or {}).get("openingDate"),
                              "A data de fundação foi incluída.", "A data de fundação foi corrigida."))

    da = ((ia.get("profile") or {}).get("description") or "").strip()
    db = ((ib.get("profile") or {}).get("description") or "").strip()
    if db and da != db:
        put("description", f"A descrição foi criada, com {len(db)} caracteres, e pensada para as buscas no Google "
                           "e nas ferramentas de inteligência artificial." if not da else
            "A descrição foi reescrita e otimizada para as buscas no Google e nas ferramentas de inteligência "
            f"artificial (antes com {len(da)} caracteres, agora com {len(db)}).")

    sa, sb = ia.get("serviceItems") or [], ib.get("serviceItems") or []
    if sb and sa != sb:
        added = len(_new(sa, sb, repr))
        put("services", f"{_pl(added, 'serviço novo incluído', 'serviços novos incluídos')} na lista "
                        f"(agora com {len(sb)})." if added else f"A lista de serviços foi atualizada (agora com {len(sb)}).")

    ma, mb = raw_before.get("media") or [], raw_after.get("media") or []
    for item_id, category, created, updated in (
            ("logo", "PROFILE", "O logotipo foi incluído.", "O logotipo foi trocado."),
            ("cover", "COVER", "A foto de capa foi incluída.", "A foto de capa foi trocada.")):
        ka = {_media_key(m) for m in ma if (m.get("locationAssociation") or {}).get("category") == category}
        kb = {_media_key(m) for m in mb if (m.get("locationAssociation") or {}).get("category") == category}
        if kb and not kb <= ka:
            put(item_id, updated if ka else created)

    new_owner = _new(ma, mb, _media_key)
    new_videos = [m for m in new_owner if m.get("mediaFormat") == "VIDEO"]
    if new_videos:
        put("videos", f"{_pl(len(new_videos), 'vídeo novo publicado', 'vídeos novos publicados')}.")
    if new_owner:
        put("owner_media", f"{_pl(len(new_owner), 'foto ou vídeo novo publicado', 'fotos e vídeos novos publicados')}"
                           " pela empresa.")
    dated = [m for m in new_owner if _year_ok(m)]
    if dated:
        put("last_owner_media", f"Fotos e vídeos novos publicados; o mais recente em {_latest(dated)}.")

    ca, cb = raw_before.get("mediaCustomers") or [], raw_after.get("mediaCustomers") or []
    new_cust = _new(ca, cb, _media_key)
    if new_cust:
        put("customer_media", f"Clientes enviaram {_pl(len(new_cust), 'foto ou vídeo novo', 'fotos e vídeos novos')}.")
    if new_owner or new_cust:
        put("total_media", f"{_pl(len(new_owner) + len(new_cust), 'foto ou vídeo novo', 'fotos e vídeos novos')} "
                           "no perfil.")

    new_posts = _new(raw_before.get("localPosts") or [], raw_after.get("localPosts") or [], _post_key)
    if new_posts:
        put("last_post", f"{_pl(len(new_posts), 'postagem nova publicada', 'postagens novas publicadas')}; "
                         f"a mais recente em {_latest(new_posts)}." if _latest(new_posts) else
            f"{_pl(len(new_posts), 'postagem nova publicada', 'postagens novas publicadas')}.")

    ra, rb = raw_before.get("reviews") or [], raw_after.get("reviews") or []
    new_reviews = _new(ra, rb, _review_key)
    if new_reviews:
        put("reviews_count", f"{_pl(len(new_reviews), 'avaliação nova', 'avaliações novas')} no período.")
    was_replied = {_review_key(r) for r in ra if _replied(r)}
    answered = sum(1 for r in rb if _replied(r) and _review_key(r) not in was_replied)
    if answered:
        put("reviews_unanswered", f"{_pl(answered, 'avaliação respondida', 'avaliações respondidas')} no período.")
    xa, xb = _rating(ra), _rating(rb)
    if xa is not None and xb is not None and xb > xa:
        put("reviews_average", f"A nota média subiu de {_num(xa)} para {_num(xb)}.")
    pa, pb = _no_comment_pct(ra), _no_comment_pct(rb)
    if pa is not None and pb is not None and pb < pa:
        put("reviews_no_comment", f"A parte das avaliações sem comentário caiu de {pa}% para {pb}%.")
    return out


def review_link(raw):
    """Link oficial para deixar uma avaliacao: o que o Google da para o perfil ou, sem ele, o do place_id."""
    meta = _info(raw).get("metadata") or {}
    uri = (meta.get("newReviewUri") or "").strip()
    if uri.startswith("https://"):
        return uri
    place = (meta.get("placeId") or "").strip()
    if place and place.replace("-", "").replace("_", "").isalnum():
        return f"https://search.google.com/local/writereview?placeid={place}"
    return None
