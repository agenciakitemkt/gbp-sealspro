"""Servico de analise: coleta -> JSON bruto -> perfil normalizado -> motor de nota -> historico."""

import threading
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

import gbp_auth as g
import storage
from collector.google import fetch_raw
from collector.normalize import normalize
from scoring import analyze


class AnalysisError(Exception):
    """Falha ao analisar um local (rede, permissao, cota...). A mensagem pode ser mostrada ao usuario."""


def run_analysis(db, location):
    """Roda uma analise nova de um local (linha de `locations`) e a guarda. Devolve a analise salva."""
    try:
        raw = fetch_raw(location["account_id"], location["id"])
    except SystemExit as e:  # gbp_auth aborta com sys.exit(mensagem) em erro de API
        raise AnalysisError(str(e.code)) from e
    except requests.RequestException as e:
        raise AnalysisError(f"Sem conexao com o Google: {e.__class__.__name__}") from e
    raw_path = storage.save_raw(db, location["id"], raw)
    store_analysis(db, location["id"], raw, raw_path)
    return storage.latest_analysis(db, location["id"])


def store_analysis(db, location_id, raw, raw_path, kind="real"):
    """Roda o motor atual sobre um bruto e guarda a analise (com versao do motor e do config). Devolve o resultado."""
    result = analyze(normalize(raw))
    storage.save_analysis(db, location_id, result, raw_path, kind=kind)
    return result


def store_pre_capture(db, capture):
    """Pre Analise: le a captura da extensao, roda o motor da Pre e guarda bruto e analise. Devolve (id, resultado)."""
    from collector_pre.maps_reader import read_capture
    from scoring.pre import analyze as analyze_pre
    from scoring.pre import version as pre_version
    profile = read_capture(capture)
    result = analyze_pre(profile)
    path = storage.save_pre_raw(profile["location"].get("id"), capture)
    analysis_id = storage.save_pre_analysis(db, profile, result, path, pre_version.PRE_ENGINE_VERSION,
                                            pre_version.config_hash(), pre_version.config_json())
    return analysis_id, result


def backfill_retroactive(db):
    """Cria analises 'retroativas' a partir dos brutos ja guardados em data/raw: calculadas AGORA com o motor atual,
    com a data da coleta do bruto. Idempotente: um bruto que ja tem analise (real ou retroativa) e pulado.

    Devolve (criadas, ja_existiam, ignorados) -- ignorados = brutos de locais que nao estao no banco.
    """
    known = {r["id"] for r in storage.list_locations(db)}
    done = {r[0] for r in db.execute("SELECT raw_path FROM analyses")}
    created = existing = ignored = 0
    for location_id in sorted(known):
        for path in storage.raw_files(location_id):
            if path in done:
                existing += 1
                continue
            raw = storage.load_raw_file(path)
            if raw is None or raw.get("location") != location_id:
                ignored += 1
                continue
            store_analysis(db, location_id, raw, path, kind="retroativa")
            created += 1
    return created, existing, ignored


class SyncError(Exception):
    """Falha ao sincronizar a lista de locais. A mensagem pode ser mostrada ao usuario."""


@dataclass
class SyncResult:
    found: int      # locais devolvidos pelo Google nesta sincronizacao
    new: int        # destes, quantos eram desconhecidos
    accounts: int
    total: int      # locais guardados no banco depois da sincronizacao


def sync_locations(db, on_progress=None):
    """Busca contas e locais no Google e atualiza a tabela `locations` (o 'active' de quem ja existe e mantido).

    `on_progress(dict)` recebe accounts_total, accounts_done, locations_found e account_name.
    E o mesmo codigo do comando `coletar.py sincronizar` e do botao da tela.
    """
    notify = on_progress or (lambda progress: None)
    try:
        accounts = g.paginate("accounts", "accounts", "accounts")
        found = new = 0
        notify({"accounts_total": len(accounts), "accounts_done": 0, "locations_found": 0, "account_name": ""})
        for i, conta in enumerate(accounts, 1):
            locais = g.paginate("info", f"{conta['name']}/locations", "locations",
                                {"readMask": "name,title,storefrontAddress", "pageSize": 100})
            for loc in locais:
                existed = db.execute("SELECT 1 FROM locations WHERE id=?", (loc["name"],)).fetchone()
                storage.upsert_location(db, loc["name"], conta["name"], loc.get("title", ""),
                                        loc.get("storefrontAddress", {}).get("locality", ""),
                                        conta.get("accountName", ""))
                new += not existed
            db.commit()
            found += len(locais)
            notify({"accounts_total": len(accounts), "accounts_done": i, "locations_found": found,
                    "account_name": conta.get("accountName", "")})
    except SystemExit as e:  # gbp_auth aborta com sys.exit(mensagem) em erro de API
        raise SyncError(str(e.code)) from e
    except requests.RequestException as e:
        raise SyncError(f"Sem conexao com o Google: {e.__class__.__name__}") from e
    return SyncResult(found, new, len(accounts), len(storage.list_locations(db)))


class SyncJob:
    """Sincronizacao em segundo plano, com estado consultavel (a tela faz polling)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = {"status": "idle"}

    def state(self):
        with self._lock:
            return dict(self._state)

    def _update(self, **fields):
        with self._lock:
            self._state.update(fields)

    def start(self):
        """Inicia a sincronizacao. False se ja houver uma em andamento."""
        with self._lock:
            if self._state["status"] == "running":
                return False
            self._state = {"status": "running", "accounts_total": None, "accounts_done": 0,
                           "locations_found": 0, "account_name": "",
                           "started_at": datetime.now(timezone.utc).isoformat()}
        threading.Thread(target=self._run, name="sync-locais", daemon=True).start()
        return True

    def _run(self):
        db = storage.connect()  # conexao propria: SQLite nao atravessa threads
        try:
            result = sync_locations(db, lambda progress: self._update(**progress))
            self._update(status="done", found=result.found, new=result.new, accounts=result.accounts,
                         total=result.total)
        except SyncError as e:
            self._update(status="error", message=str(e))
        except Exception as e:  # nunca deixar o estado preso em "running"
            self._update(status="error", message=f"Erro inesperado: {e.__class__.__name__}")
        finally:
            db.close()


sync_job = SyncJob()
