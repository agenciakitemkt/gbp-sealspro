"""Armazenamento local: SQLite para os locais (com ativo/inativo) e arquivos para o JSON bruto."""

import json
import os
import sqlite3
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")  # fora do git (dados de clientes)
DB = os.path.join(DATA, "gbp.db")

# Locais que entram inativos na primeira sincronizacao (ex-clientes, por exemplo): "locations/<id>".
EX_CLIENTES = set()


_LOCATIONS_DDL = """CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, title TEXT NOT NULL, city TEXT,
    active INTEGER NOT NULL DEFAULT 1, last_collected_at TEXT, account_name TEXT NOT NULL DEFAULT '')"""
_ANALYSES_DDL = """CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT, location_id TEXT NOT NULL REFERENCES locations(id),
    analyzed_at TEXT NOT NULL, raw_path TEXT NOT NULL, score INTEGER,
    good INTEGER NOT NULL, fair INTEGER NOT NULL, bad INTEGER NOT NULL, unavailable INTEGER NOT NULL,
    result TEXT NOT NULL,
    engine_version TEXT NOT NULL DEFAULT 'desconhecida', config_hash TEXT, config_json TEXT,
    kind TEXT NOT NULL DEFAULT 'real')"""  # kind: 'real' (coleta feita agora) | 'retroativa' (calculada depois)
_ANALYSES_INDEX = ("CREATE INDEX IF NOT EXISTS analyses_by_location_kind "
                   "ON analyses (location_id, kind, analyzed_at DESC)")
_PRE_ANALYSES_DDL = """CREATE TABLE IF NOT EXISTS pre_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT NOT NULL, place_id TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '', captured_at TEXT NOT NULL, analyzed_at TEXT NOT NULL, raw_path TEXT NOT NULL,
    score INTEGER, good INTEGER NOT NULL, fair INTEGER NOT NULL, bad INTEGER NOT NULL, unavailable INTEGER NOT NULL,
    result TEXT NOT NULL, warnings TEXT NOT NULL DEFAULT '[]',
    engine_version TEXT NOT NULL, config_hash TEXT NOT NULL, config_json TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'real')"""  # Pre Analise (CLAUDE.md, secao 13): uma linha por captura da extensao
_PRE_ANALYSES_INDEX = "CREATE INDEX IF NOT EXISTS pre_analyses_by_cid ON pre_analyses (cid, analyzed_at DESC)"
# Analise de Ranking (CLAUDE.md, secao 16). status: pendente (criada no app, esperando o clique no Maps) -> coletando
# -> pronta | erro | cancelada. points: a grade [{i, lat, lng}]; result: metricas do local e concorrentes, no fim.
_RANKINGS_DDL = """CREATE TABLE IF NOT EXISTS rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, location_id TEXT NOT NULL, keyword TEXT NOT NULL,
    grid_size INTEGER NOT NULL, radius_m INTEGER NOT NULL, view_m INTEGER NOT NULL,
    cid TEXT NOT NULL, place_id TEXT NOT NULL DEFAULT '', name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
    center_lat REAL, center_lng REAL, points TEXT, result TEXT, error TEXT,
    version TEXT NOT NULL, center_source TEXT NOT NULL DEFAULT 'maps', batch_id INTEGER,
    disabled TEXT NOT NULL DEFAULT '[]')"""
# Pontos desligados guardados por local, grade e raio (represa, mata...): as proximas analises ja nao buscam neles.
_RANKING_GRID_PREFS_DDL = """CREATE TABLE IF NOT EXISTS ranking_grid_prefs (
    location_id TEXT NOT NULL, grid_size INTEGER NOT NULL, radius_m INTEGER NOT NULL, disabled TEXT NOT NULL,
    updated_at TEXT NOT NULL, PRIMARY KEY (location_id, grid_size, radius_m))"""
_RANKINGS_INDEX = "CREATE INDEX IF NOT EXISTS rankings_by_location ON rankings (location_id, created_at DESC)"
_RANKING_POINTS_DDL = """CREATE TABLE IF NOT EXISTS ranking_points (
    ranking_id INTEGER NOT NULL REFERENCES rankings(id), idx INTEGER NOT NULL, position INTEGER,
    results TEXT NOT NULL, collected_at TEXT NOT NULL, PRIMARY KEY (ranking_id, idx))"""
# Agendamento de postagens (CLAUDE.md, secao 17). status: agendada -> publicando -> publicada | recusada | falhou;
# atrasada = venceu ha mais de LATE_HOLD_HOURS sem tentativa (espera o usuario). Horarios em UTC (ISO).
_POSTS_DDL = """CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, location_id TEXT NOT NULL, summary TEXT NOT NULL,
    cta_type TEXT NOT NULL DEFAULT '', cta_url TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
    scheduled_at TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0, first_try_at TEXT, last_try_at TEXT, next_try_at TEXT, published_at TEXT,
    media_name TEXT, image_url TEXT, post_name TEXT, search_url TEXT, google_state TEXT,
    error TEXT, error_kind TEXT)"""
_POSTS_INDEX = "CREATE INDEX IF NOT EXISTS posts_by_location ON posts (location_id, scheduled_at)"
# Busca de Leads (CLAUDE.md, secao 18). status: pendente (criada no app) -> coletando -> pronta | erro | cancelada.
# region: o retangulo do OpenStreetMap; requests: [[lat, lng, inicio], ...] que a extensao faz; result: os leads.
_LEAD_SEARCHES_DDL = """CREATE TABLE IF NOT EXISTS lead_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT NOT NULL, region_text TEXT NOT NULL, region TEXT NOT NULL,
    scope TEXT NOT NULL, grid_size INTEGER NOT NULL, pages INTEGER NOT NULL, view_m INTEGER NOT NULL,
    requests TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
    result TEXT, error TEXT, version TEXT NOT NULL)"""
# Uma linha por pedido da extensao (ponto e pagina). organic = resultados organicos na pagina; -1 = pagina pulada
# (a anterior do mesmo ponto veio com menos de 20); results NULL = resposta ilegivel.
_LEAD_PAGES_DDL = """CREATE TABLE IF NOT EXISTS lead_pages (
    search_id INTEGER NOT NULL REFERENCES lead_searches(id), idx INTEGER NOT NULL, organic INTEGER NOT NULL,
    results TEXT, collected_at TEXT NOT NULL, PRIMARY KEY (search_id, idx))"""
# Notas e favoritos valem para o negocio (chave = place_id ou CID), em todas as buscas.
_LEAD_NOTES_DDL = """CREATE TABLE IF NOT EXISTS lead_notes (
    key TEXT PRIMARY KEY, note TEXT NOT NULL, updated_at TEXT NOT NULL)"""
_LEAD_FAVORITES_DDL = """CREATE TABLE IF NOT EXISTS lead_favorites (
    key TEXT PRIMARY KEY, lead TEXT NOT NULL, search_id INTEGER, created_at TEXT NOT NULL)"""
_NEW_COLUMNS = {  # coluna -> (tabela, definicao): adicionadas em bancos criados antes da Fase 5a
    "account_name": ("locations", "TEXT NOT NULL DEFAULT ''"),
    "engine_version": ("analyses", "TEXT NOT NULL DEFAULT 'desconhecida'"),
    "config_hash": ("analyses", "TEXT"),
    "config_json": ("analyses", "TEXT"),
    "kind": ("analyses", "TEXT NOT NULL DEFAULT 'real'"),
    # Ranking: de onde veio o centro da grade ('maps' = pin do perfil; 'endereco'/'bairro'/'cidade' = endereco
    # cadastrado, para perfis sem endereco publico no Maps)
    "center_source": ("rankings", "TEXT NOT NULL DEFAULT 'maps'"),
    # Ranking: varias palavras-chave de uma vez = um lote (batch_id = id da primeira analise do lote)
    "batch_id": ("rankings", "INTEGER"),
    # Ranking: pontos da grade desligados (indices), fora da coleta e das metricas
    "disabled": ("rankings", "TEXT NOT NULL DEFAULT '[]'"),
}


def _pending_migrations(db):
    """Colunas que faltam em tabelas que ja existem (banco criado por uma versao anterior), e a tabela da Pre Analise
    num banco que ja tem dados (('pre_analyses', None, None))."""
    existing = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    pending = [("pre_analyses", None, None)] if "analyses" in existing and "pre_analyses" not in existing else []
    for column, (table, definition) in _NEW_COLUMNS.items():
        if table in existing and column not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
            pending.append((table, column, definition))
    return pending


def backup_database(db):
    """Copia consistente do banco em data/backups/ (API de backup do SQLite). Devolve o caminho."""
    folder = os.path.join(DATA, "backups")
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path, n = os.path.join(folder, f"gbp-{stamp}-antes-da-migracao.db"), 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, f"gbp-{stamp}-{n}-antes-da-migracao.db")
    target = sqlite3.connect(path)
    try:
        db.backup(target)
    finally:
        target.close()
    return path


def connect():
    """Abre o banco. Se ele veio de uma versao anterior, faz uma copia em data/backups/ ANTES de migrar."""
    os.makedirs(DATA, exist_ok=True)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    pending = _pending_migrations(db)
    if pending:
        backup_database(db)
        for table, column, definition in pending:
            if column:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        db.commit()
    db.execute(_LOCATIONS_DDL)
    db.execute(_ANALYSES_DDL)
    db.execute("DROP INDEX IF EXISTS analyses_by_location")
    db.execute(_ANALYSES_INDEX)
    db.execute(_PRE_ANALYSES_DDL)
    db.execute(_PRE_ANALYSES_INDEX)
    db.execute(_RANKINGS_DDL)  # tabelas novas: criar nao mexe em nada do que ja existe
    db.execute(_RANKINGS_INDEX)
    db.execute(_RANKING_POINTS_DDL)
    db.execute(_RANKING_GRID_PREFS_DDL)
    db.execute(_POSTS_DDL)
    db.execute(_POSTS_INDEX)
    db.execute(_LEAD_SEARCHES_DDL)
    db.execute(_LEAD_PAGES_DDL)
    db.execute(_LEAD_NOTES_DDL)
    db.execute(_LEAD_FAVORITES_DDL)
    return db


def upsert_location(db, loc_id, account_id, title, city, account_name=""):
    """Novo local entra ativo (inativo se for ex-cliente conhecido). Local existente mantem o 'active'."""
    db.execute("""INSERT INTO locations (id, account_id, title, city, active, account_name) VALUES (?, ?, ?, ?, ?, ?)
                  ON CONFLICT(id) DO UPDATE SET account_id=excluded.account_id,
                  title=excluded.title, city=excluded.city, account_name=excluded.account_name""",
               (loc_id, account_id, title, city, 0 if loc_id in EX_CLIENTES else 1, account_name))


def set_active(db, loc_id, active):
    db.execute("UPDATE locations SET active=? WHERE id=?", (int(active), loc_id))


def list_locations(db, only_active=False):
    sql = "SELECT * FROM locations" + (" WHERE active=1" if only_active else "") + " ORDER BY title"
    return db.execute(sql).fetchall()


def find_location(db, alvo):
    """Aceita locations/ID ou parte do titulo (deve ser unica)."""
    rows = [r for r in list_locations(db) if alvo == r["id"] or alvo.lower() in r["title"].lower()]
    if len(rows) != 1:
        raise SystemExit(f"'{alvo}' casa com {len(rows)} locais. Rode 'locais'." if rows
                         else f"Local '{alvo}' nao encontrado. Rode 'sincronizar' e 'locais'.")
    return rows[0]


def raw_root():
    """Pasta dos JSON brutos. Calculada a cada uso a partir de DATA (assim os testes isolam tudo trocando DATA)."""
    return os.path.join(DATA, "raw")


def save_raw(db, loc_id, raw):
    pasta = os.path.join(raw_root(), loc_id.replace("/", "_"))
    os.makedirs(pasta, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(pasta, f"{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    db.execute("UPDATE locations SET last_collected_at=? WHERE id=?", (raw["collectedAt"], loc_id))
    db.commit()
    return path


def latest_raw(loc_id):
    pasta = os.path.join(raw_root(), loc_id.replace("/", "_"))
    if not os.path.isdir(pasta):
        return None
    arquivos = sorted(f for f in os.listdir(pasta) if f.endswith(".json"))
    if not arquivos:
        return None
    with open(os.path.join(pasta, arquivos[-1]), encoding="utf-8") as f:
        return json.load(f)


def save_analysis(db, loc_id, result, raw_path, kind="real", engine_version=None, config_hash=None,
                  config_json=None):
    """Guarda uma analise (o historico fica: cada analise cria uma linha nova, sem poda).

    Grava junto a versao do motor e o snapshot do config com que a nota foi calculada.
    """
    from scoring import version
    o = result["overall"]
    cur = db.execute(
        """INSERT INTO analyses (location_id, analyzed_at, raw_path, score, good, fair, bad, unavailable, result,
                                 engine_version, config_hash, config_json, kind)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (loc_id, result["analyzedAt"], raw_path, o["score"], o["good"], o["fair"], o["bad"], o["unavailable"],
         json.dumps(result, ensure_ascii=False), engine_version or version.ENGINE_VERSION,
         config_hash or version.config_hash(), config_json or version.config_json(), kind))
    db.commit()
    return cur.lastrowid


def _analysis(row, with_result=False):
    d = {k: row[k] for k in ("id", "location_id", "analyzed_at", "raw_path", "score", "good", "fair", "bad",
                             "unavailable", "engine_version", "config_hash", "kind")}
    if with_result:
        d["result"] = json.loads(row["result"])
    return d


def latest_analysis(db, loc_id):
    """Ultima analise REAL do local ({'id', 'analyzed_at', 'result', ...}) ou None. Retroativas nunca contam aqui:
    a tela principal e o 'Ultima atualizacao' mostram so o que foi realmente analisado."""
    row = db.execute("SELECT * FROM analyses WHERE location_id=? AND kind='real' "
                     "ORDER BY analyzed_at DESC, id DESC LIMIT 1", (loc_id,)).fetchone()
    return None if row is None else _analysis(row, with_result=True)


def list_analyses(db, loc_id):
    """Todas as analises do local (reais e retroativas), da mais antiga para a mais nova, sem o JSON do resultado."""
    rows = db.execute("SELECT * FROM analyses WHERE location_id=? ORDER BY analyzed_at ASC, id ASC",
                      (loc_id,)).fetchall()
    return [_analysis(r) for r in rows]


def get_analysis(db, analysis_id):
    row = db.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    return None if row is None else _analysis(row, with_result=True)


# ---------------------------------------------------------------------------
# Pre Analise
# ---------------------------------------------------------------------------

def save_pre_raw(cid, capture):
    """Captura bruta da extensao em data/raw/pre/<cid>/<instante>.json (fora do git). Devolve o caminho."""
    safe = "".join(c for c in str(cid) if c.isdigit()) or "sem-cid"
    pasta = os.path.join(raw_root(), "pre", safe)
    os.makedirs(pasta, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = os.path.join(pasta, f"{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(capture, f, ensure_ascii=False)
    return path


def save_pre_analysis(db, profile, result, raw_path, engine_version, config_hash, config_json, kind="real"):
    """Guarda uma pre analise com a versao do motor, o config e os avisos da coleta (a tela os mostra)."""
    o, loc = result["overall"], profile["location"]
    cur = db.execute(
        """INSERT INTO pre_analyses (cid, place_id, name, captured_at, analyzed_at, raw_path, score, good, fair, bad,
                                     unavailable, result, warnings, engine_version, config_hash, config_json, kind)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (loc.get("id") or "", loc.get("placeId") or "", loc.get("name") or "", profile["collectedAt"],
         result["analyzedAt"], raw_path, o["score"], o["good"], o["fair"], o["bad"], o["unavailable"],
         json.dumps(result, ensure_ascii=False), json.dumps(result.get("warnings") or [], ensure_ascii=False),
         engine_version, config_hash, config_json, kind))
    db.commit()
    return cur.lastrowid


def _pre_analysis(row, with_result=False):
    d = {k: row[k] for k in ("id", "cid", "place_id", "name", "captured_at", "analyzed_at", "raw_path", "score",
                             "good", "fair", "bad", "unavailable", "engine_version", "config_hash", "kind")}
    d["warnings"] = json.loads(row["warnings"])
    if with_result:
        d["result"] = json.loads(row["result"])
    return d


def list_pre_analyses(db, limit=100):
    rows = db.execute("SELECT * FROM pre_analyses ORDER BY analyzed_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return [_pre_analysis(r) for r in rows]


def get_pre_analysis(db, analysis_id):
    row = db.execute("SELECT * FROM pre_analyses WHERE id=?", (analysis_id,)).fetchone()
    return None if row is None else _pre_analysis(row, with_result=True)


def raw_files(loc_id):
    """Caminhos dos JSON brutos guardados do local, do mais antigo para o mais novo."""
    pasta = os.path.join(raw_root(), loc_id.replace("/", "_"))
    if not os.path.isdir(pasta):
        return []
    return [os.path.join(pasta, f) for f in sorted(os.listdir(pasta)) if f.endswith(".json")]


def load_raw_file(path):
    """Le um bruto guardado. So aceita arquivos dentro de data/raw (o caminho vem do banco). None se nao existir."""
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(raw_root()) + os.sep) or not os.path.isfile(real):
        return None
    with open(real, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Analise de Ranking
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_ranking(db, location_id, keyword, grid_size, radius_m, view_m, cid, place_id, name, version):
    cur = db.execute(
        """INSERT INTO rankings (location_id, keyword, grid_size, radius_m, view_m, cid, place_id, name, status,
                                 created_at, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)""",
        (location_id, keyword, grid_size, radius_m, view_m, cid, place_id, name, _now(), version))
    db.commit()
    return cur.lastrowid


def _ranking(row):
    if row is None:
        return None
    d = dict(row)
    d["points"] = json.loads(d["points"]) if d["points"] else []
    d["result"] = json.loads(d["result"]) if d["result"] else None
    d["disabled"] = json.loads(d.get("disabled") or "[]")
    return d


def set_ranking_disabled(db, ranking_id, disabled, result=None):
    """Pontos desligados de uma analise (e o resultado recalculado, se houver)."""
    if result is None:
        db.execute("UPDATE rankings SET disabled=? WHERE id=?", (json.dumps(sorted(disabled)), ranking_id))
    else:
        db.execute("UPDATE rankings SET disabled=?, result=? WHERE id=?",
                   (json.dumps(sorted(disabled)), json.dumps(result, ensure_ascii=False), ranking_id))
    db.commit()


def grid_pref(db, location_id, grid_size, radius_m):
    row = db.execute("SELECT disabled FROM ranking_grid_prefs WHERE location_id=? AND grid_size=? AND radius_m=?",
                     (location_id, grid_size, radius_m)).fetchone()
    return json.loads(row["disabled"]) if row else []


def save_grid_pref(db, location_id, grid_size, radius_m, disabled):
    db.execute("INSERT OR REPLACE INTO ranking_grid_prefs (location_id, grid_size, radius_m, disabled, updated_at) "
               "VALUES (?, ?, ?, ?, ?)", (location_id, grid_size, radius_m, json.dumps(sorted(disabled)), _now()))
    db.commit()


def set_ranking_batch(db, ranking_ids, batch_id):
    db.executemany("UPDATE rankings SET batch_id=? WHERE id=?", [(batch_id, i) for i in ranking_ids])
    db.commit()


def list_batch(db, batch_id):
    """Analises de um lote, na ordem em que foram criadas."""
    rows = db.execute("SELECT * FROM rankings WHERE batch_id=? ORDER BY id", (batch_id,)).fetchall()
    return [_ranking(r) for r in rows]


def get_ranking(db, ranking_id):
    return _ranking(db.execute("SELECT * FROM rankings WHERE id=?", (ranking_id,)).fetchone())


def list_rankings(db, location_id):
    rows = db.execute("SELECT * FROM rankings WHERE location_id=? ORDER BY created_at DESC, id DESC",
                      (location_id,)).fetchall()
    return [_ranking(r) for r in rows]


def list_active_rankings(db):
    """Analises de ranking dos locais ativos (para o lembrete), com o nome do local em `title`."""
    rows = db.execute("SELECT r.*, l.title AS title FROM rankings r JOIN locations l ON l.id = r.location_id "
                      "WHERE l.active = 1 ORDER BY r.created_at, r.id").fetchall()
    out = []
    for row in rows:
        title = row["title"]
        d = _ranking(row)
        d["title"] = title
        out.append(d)
    return out


def pending_ranking(db, cid, since):
    """A analise pendente mais recente do local com esse CID, criada depois de `since` (ISO)."""
    row = db.execute("SELECT * FROM rankings WHERE cid=? AND status='pendente' AND created_at>=? "
                     "ORDER BY created_at DESC, id DESC LIMIT 1", (cid, since)).fetchone()
    return _ranking(row)


def start_ranking(db, ranking_id, lat, lng, points, center_source="maps"):
    db.execute("UPDATE rankings SET status='coletando', started_at=?, center_lat=?, center_lng=?, points=?, "
               "center_source=? WHERE id=? AND status='pendente'",
               (_now(), lat, lng, json.dumps(points), center_source, ranking_id))
    db.commit()


def save_ranking_point(db, ranking_id, idx, position, results):
    db.execute("INSERT OR REPLACE INTO ranking_points (ranking_id, idx, position, results, collected_at) "
               "VALUES (?, ?, ?, ?, ?)", (ranking_id, idx, position, json.dumps(results, ensure_ascii=False), _now()))
    db.commit()


def ranking_points(db, ranking_id):
    """{idx: {"position", "results"}} dos pontos ja recebidos."""
    rows = db.execute("SELECT idx, position, results FROM ranking_points WHERE ranking_id=? ORDER BY idx",
                      (ranking_id,)).fetchall()
    return {r["idx"]: {"position": r["position"], "results": json.loads(r["results"])} for r in rows}


def count_ranking_points(db, ranking_id):
    return db.execute("SELECT COUNT(*) FROM ranking_points WHERE ranking_id=?", (ranking_id,)).fetchone()[0]


def finish_ranking(db, ranking_id, status, result=None, error=None):
    db.execute("UPDATE rankings SET status=?, finished_at=?, result=?, error=? WHERE id=?",
               (status, _now(), json.dumps(result, ensure_ascii=False) if result is not None else None, error,
                ranking_id))
    db.commit()


def save_ranking_raw(ranking_id, idx, text):
    """Resposta bruta de um ponto em data/raw/ranking/<id>/<idx>.json.gz (fora do git; cerca de 230 KB sem compactar)."""
    import gzip
    pasta = os.path.join(raw_root(), "ranking", str(int(ranking_id)))
    os.makedirs(pasta, exist_ok=True)
    path = os.path.join(pasta, f"{int(idx):03d}.json.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------------------
# Busca de Leads (CLAUDE.md, secao 18)
# ---------------------------------------------------------------------------

def create_lead_search(db, keyword, region_text, region, scope, grid_size, pages, view_m, requests, version):
    cur = db.execute(
        """INSERT INTO lead_searches (keyword, region_text, region, scope, grid_size, pages, view_m, requests, status,
                                      created_at, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)""",
        (keyword, region_text, json.dumps(region, ensure_ascii=False), scope, grid_size, pages, view_m,
         json.dumps(requests), _now(), version))
    db.commit()
    return cur.lastrowid


def _lead_search(row):
    if row is None:
        return None
    d = dict(row)
    d["region"] = json.loads(d["region"])
    d["requests"] = json.loads(d["requests"])
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


def get_lead_search(db, search_id):
    return _lead_search(db.execute("SELECT * FROM lead_searches WHERE id=?", (search_id,)).fetchone())


def list_lead_searches(db, limit=100):
    """Buscas mais recentes primeiro, sem os leads (so o total)."""
    rows = db.execute("SELECT id, keyword, region_text, scope, status, created_at, finished_at, error, "
                      "json_extract(result, '$.total') AS total FROM lead_searches ORDER BY id DESC LIMIT ?",
                      (limit,)).fetchall()
    return [dict(r) for r in rows]


def start_lead_search(db, search_id):
    db.execute("UPDATE lead_searches SET status='coletando', started_at=? WHERE id=? AND status='pendente'",
               (_now(), search_id))
    db.commit()


def save_lead_page(db, search_id, idx, organic, results):
    db.execute("INSERT OR REPLACE INTO lead_pages (search_id, idx, organic, results, collected_at) VALUES "
               "(?, ?, ?, ?, ?)", (search_id, idx, organic,
                                   None if results is None else json.dumps(results, ensure_ascii=False), _now()))
    db.commit()


def lead_pages(db, search_id):
    """{idx: {"organic", "results"}} dos pedidos ja recebidos (ou pulados)."""
    rows = db.execute("SELECT idx, organic, results FROM lead_pages WHERE search_id=? ORDER BY idx",
                      (search_id,)).fetchall()
    return {r["idx"]: {"organic": r["organic"], "results": json.loads(r["results"]) if r["results"] else None}
            for r in rows}


def count_lead_pages(db, search_id):
    return db.execute("SELECT COUNT(*) FROM lead_pages WHERE search_id=?", (search_id,)).fetchone()[0]


def finish_lead_search(db, search_id, status, result=None, error=None):
    db.execute("UPDATE lead_searches SET status=?, finished_at=?, result=?, error=? WHERE id=?",
               (status, _now(), json.dumps(result, ensure_ascii=False) if result is not None else None, error,
                search_id))
    db.commit()


def delete_lead_search(db, search_id):
    """Apaga a busca e as paginas dela (notas e favoritos ficam, porque sao do negocio)."""
    db.execute("DELETE FROM lead_pages WHERE search_id=?", (search_id,))
    db.execute("DELETE FROM lead_searches WHERE id=?", (search_id,))
    db.commit()


def save_lead_raw(search_id, idx, text):
    """Resposta bruta de um pedido em data/raw/leads/<id>/<idx>.json.gz (fora do git)."""
    import gzip
    pasta = os.path.join(raw_root(), "leads", str(int(search_id)))
    os.makedirs(pasta, exist_ok=True)
    path = os.path.join(pasta, f"{int(idx):03d}.json.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(text)
    return path


def lead_notes(db):
    return {r["key"]: r["note"] for r in db.execute("SELECT key, note FROM lead_notes")}


def save_lead_note(db, key, note):
    """Nota vazia apaga a nota."""
    if note:
        db.execute("INSERT OR REPLACE INTO lead_notes (key, note, updated_at) VALUES (?, ?, ?)", (key, note, _now()))
    else:
        db.execute("DELETE FROM lead_notes WHERE key=?", (key,))
    db.commit()


def lead_favorites(db):
    """{key: lead} dos favoritos, do mais recente para o mais antigo."""
    rows = db.execute("SELECT key, lead, search_id FROM lead_favorites ORDER BY created_at DESC").fetchall()
    return {r["key"]: {**json.loads(r["lead"]), "searchId": r["search_id"]} for r in rows}


def set_lead_favorite(db, key, lead, search_id, on):
    if on:
        db.execute("INSERT OR REPLACE INTO lead_favorites (key, lead, search_id, created_at) VALUES (?, ?, ?, ?)",
                   (key, json.dumps(lead, ensure_ascii=False), search_id, _now()))
    else:
        db.execute("DELETE FROM lead_favorites WHERE key=?", (key,))
    db.commit()


# ---------------------------------------------------------------------------
# Agendamento de postagens (CLAUDE.md, secao 17)
# ---------------------------------------------------------------------------

POST_FIELDS = ("summary", "cta_type", "cta_url", "image", "scheduled_at")


def create_post(db, location_id, summary, cta_type, cta_url, image, scheduled_at):
    now = _now()
    cur = db.execute("""INSERT INTO posts (location_id, summary, cta_type, cta_url, image, scheduled_at, status,
                        created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'agendada', ?, ?)""",
                     (location_id, summary, cta_type, cta_url, image, scheduled_at, now, now))
    db.commit()
    return cur.lastrowid


def get_post(db, post_id):
    row = db.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    return dict(row) if row else None


def list_posts(db, location_id, start=None, end=None):
    """Postagens do local; com start/end (UTC ISO), so as agendadas nesse intervalo [start, end)."""
    sql, args = "SELECT * FROM posts WHERE location_id=?", [location_id]
    if start:
        sql, args = sql + " AND scheduled_at >= ?", args + [start]
    if end:
        sql, args = sql + " AND scheduled_at < ?", args + [end]
    return [dict(r) for r in db.execute(sql + " ORDER BY scheduled_at, id", args)]


def update_post(db, post_id, **fields):
    """Atualiza colunas da postagem (nomes vindos so do codigo, nunca da tela)."""
    allowed = set(POST_FIELDS) | {"status", "attempts", "first_try_at", "last_try_at", "next_try_at",
                                  "published_at", "media_name", "image_url", "post_name", "search_url",
                                  "google_state", "error", "error_kind"}
    assert set(fields) <= allowed, set(fields) - allowed
    cols = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE posts SET {cols}, updated_at=? WHERE id=?", (*fields.values(), _now(), post_id))
    db.commit()


def claim_post(db, post_id, now, from_status=("agendada", "atrasada", "falhou")):
    """Marca a postagem como 'publicando' so se ninguem pegou antes (o app e o publicador podem rodar juntos).
    Devolve a linha atualizada ou None."""
    marks = ",".join("?" * len(from_status))
    cur = db.execute(f"""UPDATE posts SET status='publicando', attempts=attempts+1, last_try_at=?,
                         first_try_at=COALESCE(first_try_at, ?), updated_at=? WHERE id=? AND status IN ({marks})""",
                     (now, now, now, post_id, *from_status))
    db.commit()
    return get_post(db, post_id) if cur.rowcount == 1 else None


def delete_post(db, post_id):
    db.execute("DELETE FROM posts WHERE id=?", (post_id,))
    db.commit()


def posts_where(db, sql, args=()):
    return [dict(r) for r in db.execute(f"SELECT * FROM posts WHERE {sql}", args)]


def images_in_use(db):
    return {r[0] for r in db.execute("SELECT DISTINCT image FROM posts WHERE image != ''")}
