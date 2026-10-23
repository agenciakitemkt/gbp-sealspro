"""Fluxo da Analise de Ranking no app (CLAUDE.md, secao 16):
1. new_ranking: o usuario escolhe cliente, palavra, grade e raio na tela; a analise fica "pendente".
2. begin: no perfil do cliente no Google Maps, o clique no botao "Ranking SealsPro" faz a extensao mandar a resposta
   preview/place da pagina; o app confere que e o cliente, le o centro e monta a grade ("coletando").
3. add_point: a extensao manda a busca de cada ponto; o app le e guarda (bruto compactado em data/raw/ranking/).
4. finish: com todos os pontos, calcula as metricas do cliente e dos concorrentes ("pronta").
"""

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, quote, urlsplit

import storage
from collector_pre.maps_reader import Reading, read_place
from ranking import config, grid, metrics, reader
from ranking.geocode import geocode_address

MAX_COMPETITORS = 200


class RankingError(Exception):
    """Mensagem em portugues, para mostrar na tela ou na faixa da extensao."""


def client_identity(location_id):
    """CID, place_id, nome e categoria do cliente, do ultimo bruto da Analise Completa (o mapsUri traz ?cid=)."""
    raw = storage.latest_raw(location_id)
    if not raw:
        raise RankingError("Este local ainda não tem coleta. Rode a Análise Completa uma vez antes do ranking.")
    info = raw.get("info") or {}
    meta = info.get("metadata") or {}
    cid = (parse_qs(urlsplit(meta.get("mapsUri") or "").query).get("cid") or [""])[0]
    if not cid.isdigit():
        raise RankingError("Não foi possível achar o identificador do perfil no Google (CID) na última coleta.")
    category = ((info.get("categories") or {}).get("primaryCategory") or {}).get("displayName", "")
    return {"cid": cid, "placeId": meta.get("placeId") or "", "name": info.get("title") or "", "category": category,
            "mapsUrl": f"https://www.google.com/maps?cid={cid}&hl=pt-BR"}


def clean_keyword(keyword):
    kw = re.sub(r"\s+", " ", keyword or "").strip()
    if not kw:
        raise RankingError("Informe a palavra-chave.")
    if len(kw) > config.KEYWORD_MAX:
        raise RankingError(f"Palavra-chave longa demais (máximo {config.KEYWORD_MAX} caracteres).")
    return kw


def new_ranking(db, location, keyword, grid_size, radius_m, view_m=config.VIEW_DISTANCE_M):
    """Cria a analise pendente. location: linha da tabela locations (ativa)."""
    if view_m not in config.VIEW_OPTIONS_M:
        raise RankingError("Zoom inválido.")
    if grid_size not in config.GRID_SIZES:
        raise RankingError("Tamanho de grade inválido.")
    if not config.RADIUS_MIN_M <= radius_m <= config.RADIUS_MAX_M:
        raise RankingError("Raio inválido.")
    ident = client_identity(location["id"])
    rid = storage.create_ranking(db, location["id"], clean_keyword(keyword), grid_size, radius_m,
                                 view_m, ident["cid"], ident["placeId"], ident["name"],
                                 config.RANKING_VERSION)
    disabled = storage.grid_pref(db, location["id"], grid_size, radius_m)
    if disabled:  # pontos desligados antes nesta grade (represa, mata...): nem sao buscados
        storage.set_ranking_disabled(db, rid, disabled)
    return rid


def split_keywords(text):
    """Texto do formulario -> palavras-chave (sem repetir, na ordem). Separadores: virgula, ponto e virgula, linha."""
    out, seen = [], set()
    for part in re.split(r"[,;\n]+", text or ""):
        kw = re.sub(r"\s+", " ", part).strip()
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            out.append(kw)
    if not out:
        raise RankingError("Informe a palavra-chave.")
    if len(out) > config.BATCH_MAX:
        raise RankingError(f"No máximo {config.BATCH_MAX} palavras-chave por vez.")
    return out


def new_batch(db, location, keywords_text, grid_size, radius_m, view_m=config.VIEW_DISTANCE_M):
    """Uma analise pendente por palavra-chave. Com mais de uma, ficam no mesmo lote (batch_id = a primeira).
    Devolve (ids, batch_id ou None)."""
    keywords = split_keywords(keywords_text)
    for kw in keywords:
        clean_keyword(kw)  # valida todas antes de criar qualquer uma
    ids = [new_ranking(db, location, kw, grid_size, radius_m, view_m) for kw in keywords]
    if len(ids) == 1:
        return ids, None
    storage.set_ranking_batch(db, ids, ids[0])
    return ids, ids[0]


def repeat_batch(db, batch_id):
    """Repete todas as palavras de um lote, com a mesma grade, raio e zoom (um lote novo)."""
    items = storage.list_batch(db, batch_id)
    if not items:
        raise RankingError("Lote não encontrado.")
    first = items[0]
    location = next((l for l in storage.list_locations(db, only_active=True) if l["id"] == first["location_id"]), None)
    if location is None:
        raise RankingError("O local deste lote não está mais ativo.")
    view = first["view_m"] if first["view_m"] in config.VIEW_OPTIONS_M else config.VIEW_DISTANCE_M
    return new_batch(db, location, ", ".join(r["keyword"] for r in items), first["grid_size"], first["radius_m"], view)


def next_in_batch(db, done):
    """Depois de uma analise do lote: inicia a proxima pendente do mesmo lote com o mesmo centro (o perfil e o mesmo,
    nao precisa abrir de novo) e devolve a tarefa dela. None se nao houver."""
    if not done or not done.get("batch_id") or done.get("center_lat") is None:
        return None
    for r in storage.list_batch(db, done["batch_id"]):
        if r["status"] == "pendente" and r["id"] > done["id"] and r["created_at"] >= _pending_since():
            points = grid.make_grid(done["center_lat"], done["center_lng"], r["grid_size"], r["radius_m"])
            storage.start_ranking(db, r["id"], done["center_lat"], done["center_lng"], points, done["center_source"])
            return task(storage.get_ranking(db, r["id"]))
    return None


def search_url(keyword, lat, lng):
    """Busca da palavra no Maps, perto do centro: a pagina traz o modelo do pedido tbm=map (preload) que a extensao usa
    em cada ponto, trocando so as coordenadas e a distancia de visao."""
    return (f"https://www.google.com/maps/search/{quote(keyword, safe='').replace('%20', '+')}/"
            f"@{lat:.7f},{lng:.7f},15z?hl=pt-BR")


def enabled_points(ranking):
    """Indices da grade que sao buscados (sem os desligados), na ordem da grade."""
    off = set(ranking.get("disabled") or [])
    return [i for i in range(len(ranking["points"])) if i not in off]


def task(ranking):
    """O que a extensao precisa para os pontos (nada alem disso sai do app). So os pontos ligados: a extensao numera
    de 0 em diante e o app converte para o indice da grade (add_point)."""
    return {"id": ranking["id"], "keyword": ranking["keyword"], "view": ranking["view_m"],
            "points": [[round(ranking["points"][i]["lat"], 7), round(ranking["points"][i]["lng"], 7)]
                       for i in enabled_points(ranking)],
            "searchUrl": search_url(ranking["keyword"], ranking["center_lat"], ranking["center_lng"])}


def _pending_since():
    return (datetime.now(timezone.utc) - timedelta(minutes=config.PENDING_TTL_MIN)).isoformat(timespec="seconds")


def set_disabled(db, ranking_id, disabled):
    """Desliga/religa pontos de uma analise pronta: recalcula as metricas com os pontos ja guardados e guarda a escolha
    para as proximas analises do mesmo local, grade e raio. Ponto religado que nao foi buscado fica "sem leitura"."""
    r = storage.get_ranking(db, ranking_id)
    if r is None or r["status"] != "pronta":
        raise RankingError("Só dá para mudar os pontos de uma análise pronta.")
    n = len(r["points"])
    if not isinstance(disabled, list) or not all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < n
                                                 for i in disabled):
        raise RankingError("Pontos inválidos.")
    disabled = sorted(set(disabled))
    if len(disabled) >= n:
        raise RankingError("Deixe ao menos um ponto ligado.")
    r["disabled"] = disabled
    result = build_result(r, storage.ranking_points(db, ranking_id))
    for k in ("warning",):
        if r["result"] and k in r["result"]:
            result[k] = r["result"][k]
    storage.set_ranking_disabled(db, ranking_id, disabled, result)
    storage.save_grid_pref(db, r["location_id"], r["grid_size"], r["radius_m"], disabled)
    return result


def shown_status(ranking):
    """Situacao para a tela: uma analise pendente que passou do prazo aparece como "expirada" (nao e mais aceita)."""
    if ranking["status"] == "pendente" and ranking["created_at"] < _pending_since():
        return "expirada"
    return ranking["status"]


def repeat(db, ranking_id):
    """Nova analise pendente com a mesma palavra, grade e raio de uma analise anterior do mesmo local."""
    old = storage.get_ranking(db, ranking_id)
    if old is None:
        raise RankingError("Análise não encontrada.")
    location = next((l for l in storage.list_locations(db, only_active=True) if l["id"] == old["location_id"]), None)
    if location is None:
        raise RankingError("O local desta análise não está mais ativo.")
    view = old["view_m"] if old["view_m"] in config.VIEW_OPTIONS_M else config.VIEW_DISTANCE_M
    return new_ranking(db, location, old["keyword"], old["grid_size"], old["radius_m"], view)


def pending_task(db, ranking_id):
    """Clique em "Analisar" no app: a extensao pergunta qual perfil abrir no Maps para a analise pendente."""
    ranking = storage.get_ranking(db, ranking_id)
    if ranking is None or ranking["status"] != "pendente" or ranking["created_at"] < _pending_since():
        raise RankingError("esta análise não está mais esperando. Prepare outra no app.")
    return {"id": ranking["id"], "mapsUrl": f"https://www.google.com/maps?cid={ranking['cid']}&hl=pt-BR"}


def geocode(address):
    """Indirecao para os testes trocarem o geocodificador (sem internet)."""
    return geocode_address(address)


def begin(db, place_raw, ranking_id=None):
    """Perfil aberto no Maps (pelo clique no app ou no botao "Ranking SealsPro"): acha a analise pendente desse perfil,
    le o centro e monta a grade. Devolve a tarefa. ranking_id: a analise que a extensao abriu (tem de ser a mesma)."""
    location, *_ = read_place(place_raw, Reading()) or (None,)
    if not location or not location.get("id"):
        raise RankingError("não foi possível ler o perfil aberto no Maps. Recarregue a página e tente de novo.")
    if ranking_id is not None:  # aberta pela extensao para esta analise (clique no app): tem de ser deste perfil
        ranking = storage.get_ranking(db, ranking_id)
        if ranking is None or ranking["status"] != "pendente" or ranking["created_at"] < _pending_since():
            raise RankingError("esta análise não está mais esperando. Prepare outra no app.")
        if ranking["cid"] != location["id"]:
            raise RankingError("o perfil aberto no Maps não é o do cliente desta análise.")
    else:  # botao "Ranking SealsPro" no perfil: a pendente mais recente; num lote, a primeira palavra que falta
        ranking = storage.pending_ranking(db, location["id"], _pending_since())
        if ranking is not None and ranking.get("batch_id"):
            ranking = next(r for r in storage.list_batch(db, ranking["batch_id"]) if r["status"] == "pendente")
    if ranking is None:
        raise RankingError("não há análise de ranking esperando para este perfil. Crie a análise no app "
                           "(127.0.0.1:8000/ranking) e clique de novo.")
    lat, lng, source = location.get("lat"), location.get("lng"), "maps"
    if not location.get("address"):
        # Perfil sem endereco publico (area de atendimento): o Maps poe o pin no centro do pais. O centro vem do
        # endereco cadastrado na conta do Google (ranking/geocode.py).
        raw = storage.latest_raw(ranking["location_id"]) or {}
        found = geocode(((raw.get("info") or {}).get("storefrontAddress")))
        if not found:
            storage.finish_ranking(db, ranking["id"], "erro", error="Este perfil não tem endereço público no Maps e "
                                   "não foi possível localizar o endereço cadastrado na conta do Google.")
            raise RankingError("este perfil não tem endereço público no Maps e o endereço cadastrado não foi "
                               "localizado. Veja a análise no app.")
        lat, lng, source = found
    points = grid.make_grid(lat, lng, ranking["grid_size"], ranking["radius_m"])
    storage.start_ranking(db, ranking["id"], lat, lng, points, source)
    return task(storage.get_ranking(db, ranking["id"]))


def _collecting(db, ranking_id):
    ranking = storage.get_ranking(db, ranking_id)
    if ranking is None or ranking["status"] != "coletando":
        raise RankingError("análise de ranking não está em coleta.")
    return ranking


def add_point(db, ranking_id, idx, text):
    """Um ponto da grade. Resposta ilegivel fica guardada como None (o ponto sai das metricas, com aviso)."""
    ranking = _collecting(db, ranking_id)
    enabled = enabled_points(ranking)
    if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx < len(enabled):
        raise RankingError("ponto fora da grade.")
    idx = enabled[idx]  # numero do pedido -> indice da grade
    storage.save_ranking_raw(ranking_id, idx, text)
    results = reader.read_point(text)
    pos = reader.position(results, ranking["place_id"], ranking["cid"]) if results is not None else None
    storage.save_ranking_point(db, ranking_id, idx, pos, results)
    return {"received": storage.count_ranking_points(db, ranking_id), "total": len(enabled)}


def build_result(ranking, received):
    """Metricas do cliente e dos concorrentes a partir dos pontos lidos. Pontos sem resposta ou ilegiveis ficam fora
    das metricas (avisados em `unread`); as posicoes por ponto vem na ordem da grade (None = fora dos 20)."""
    n = len(ranking["points"])
    off = set(ranking.get("disabled") or [])
    readable = [i for i in range(n) if i not in off and i in received and received[i]["results"] is not None]
    unread = [i for i in range(n) if i not in off and i not in readable]
    comps = metrics.competitors([received[i]["results"] for i in readable])

    def full(positions):
        out = [None] * n
        for k, i in enumerate(readable):
            out[i] = positions[k]
        return out

    own_positions = [reader.position(received[i]["results"], ranking["place_id"], ranking["cid"]) for i in readable]
    own = {**metrics.summary(own_positions), "positions": full(own_positions)}
    own_rank = next((k for k, c in enumerate(comps, 1) if reader.same_place(c, ranking["place_id"], ranking["cid"])),
                    None)
    competitors = [{**c, "positions": full(c["positions"]), "own": reader.same_place(c, ranking["place_id"],
                                                                                       ranking["cid"])}
                   for c in comps[:MAX_COMPETITORS]]
    return {"own": own, "ownRank": own_rank, "competitors": competitors, "competitorsTotal": len(comps),
            "unread": unread, "disabled": sorted(off)}


def finish(db, ranking_id, cancelled=False, error=None):
    """Fim da coleta. Cancelada ou com erro: guarda o motivo (vale tambem antes de comecar, ainda pendente, para a
    tela do app mostrar o que deu errado). Senao, calcula e grava o resultado. Devolve a situacao final."""
    status, _next = finish_and_next(db, ranking_id, cancelled, error)
    return status


def finish_and_next(db, ranking_id, cancelled=False, error=None):
    """Como finish, e ainda: num lote, cancelar cancela as palavras que faltam; senao, inicia a proxima palavra
    (mesmo com erro nesta). Devolve (situacao, tarefa da proxima ou None)."""
    status = _finish(db, ranking_id, cancelled, error)
    done = storage.get_ranking(db, ranking_id)
    if done and done.get("batch_id"):
        blocked = bool(error) and str(error).startswith(config.BLOCKED_PREFIX)
        if cancelled or blocked:
            for r in storage.list_batch(db, done["batch_id"]):
                if r["status"] == "pendente":
                    storage.finish_ranking(db, r["id"], "cancelada", error="Lote cancelado no Maps." if cancelled else
                                           "Não rodou: o Google pediu verificação (captcha) na palavra anterior.")
            return status, None
        return status, next_in_batch(db, done)
    return status, None


def _finish(db, ranking_id, cancelled=False, error=None):
    ranking = storage.get_ranking(db, ranking_id)
    if ranking is not None and ranking["status"] == "pendente" and (cancelled or error):
        storage.finish_ranking(db, ranking_id, "cancelada" if cancelled else "erro",
                               error="Cancelada no Maps." if cancelled else str(error)[:300])
        return "cancelada" if cancelled else "erro"
    ranking = _collecting(db, ranking_id)
    received = storage.ranking_points(db, ranking_id)
    if cancelled:
        storage.finish_ranking(db, ranking_id, "cancelada", error="Cancelada no Maps.")
        return "cancelada"
    if error:
        storage.finish_ranking(db, ranking_id, "erro", error=str(error)[:300])
        return "erro"
    missing = len(enabled_points(ranking)) - len(received)
    result = build_result(ranking, received)
    if len(result["unread"]) == len(enabled_points(ranking)):
        storage.finish_ranking(db, ranking_id, "erro", error="Nenhum ponto pôde ser lido (o formato da busca do Maps "
                                                             "pode ter mudado).")
        return "erro"
    if missing:
        result["warning"] = f"{missing} ponto(s) não chegaram e ficaram fora das métricas."
    storage.finish_ranking(db, ranking_id, "pronta", result=result)
    return "pronta"
