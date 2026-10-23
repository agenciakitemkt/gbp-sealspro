"""Fase 0: credenciais OAuth (escopo business.manage) e chamadas REST ao Google Business Profile."""

import os
import re
import sys
import time

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPE = "https://www.googleapis.com/auth/business.manage"
TOKEN_URI = "https://oauth2.googleapis.com/token"
HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")
# Fallback opcional, somente leitura: o .env de uma skill google-business-profile local, se existir.
FALLBACK_ENV = os.path.join(HERE, ".claude", "skills", "google-business-profile", ".env")

API = {
    "accounts": "https://mybusinessaccountmanagement.googleapis.com/v1",
    "info": "https://mybusinessbusinessinformation.googleapis.com/v1",
    "v4": "https://mybusiness.googleapis.com/v4",
}


def _read_env(path):
    out = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_config():
    cfg = {}
    for path in (FALLBACK_ENV, ENV_PATH):  # o .env do projeto tem prioridade
        cfg.update({k: v for k, v in _read_env(path).items() if v})
    return cfg


def project_env():
    """So o .env da raiz do projeto (sem o da skill). As chaves da extensao (GBP_EXTENSION_*) vivem so nele."""
    return {k: v for k, v in _read_env(ENV_PATH).items() if v}


def save_env_value(key, value, path=None):
    """Grava (ou troca) KEY="valor" no .env do projeto, com permissao so do dono (600)."""
    path = path or ENV_PATH
    text = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    line = f'{key}="{value}"'
    pattern = rf"^{re.escape(key)}=.*$"
    if re.search(pattern, text, re.M):
        text = re.sub(pattern, lambda _m: line, text, flags=re.M)
    else:
        text = text.rstrip("\n") + ("\n" if text else "") + line + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, 0o600)


def save_refresh_token(token):
    save_env_value("GBP_REFRESH_TOKEN", token)


def login():
    """Abre o navegador, autoriza business.manage e grava o refresh token no .env do projeto."""
    cfg = load_config()
    if not (cfg.get("GBP_CLIENT_ID") and cfg.get("GBP_CLIENT_SECRET")):
        sys.exit("Faltam GBP_CLIENT_ID e GBP_CLIENT_SECRET (copie .env.example para .env).")
    client = {"installed": {
        "client_id": cfg["GBP_CLIENT_ID"], "client_secret": cfg["GBP_CLIENT_SECRET"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": TOKEN_URI,
    }}
    # Client compartilhado com o Google Ads: o Google devolve escopos extras ja concedidos.
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow = InstalledAppFlow.from_client_config(client, scopes=[SCOPE])
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent",
                                  include_granted_scopes="false")
    if not creds.refresh_token:
        sys.exit("O Google nao devolveu refresh token. Revogue o app em myaccount.google.com/permissions e repita.")
    save_refresh_token(creds.refresh_token)
    print(f"Refresh token gravado em {ENV_PATH}")


_creds = None


def _token():
    global _creds
    if _creds is None:
        cfg = load_config()
        for k in ("GBP_CLIENT_ID", "GBP_CLIENT_SECRET", "GBP_REFRESH_TOKEN"):
            if not cfg.get(k):
                sys.exit(f"Falta {k}. Rode: python3 fase0.py login")
        _creds = Credentials(None, refresh_token=cfg["GBP_REFRESH_TOKEN"], token_uri=TOKEN_URI,
                             client_id=cfg["GBP_CLIENT_ID"], client_secret=cfg["GBP_CLIENT_SECRET"],
                             scopes=[SCOPE])
    if not _creds.valid:
        _creds.refresh(Request())
    return _creds.token


def get(api, path, params=None, soft=False):
    """GET autenticado. Com soft=True devolve {'_erro': ...} em vez de abortar (para sondar cada API)."""
    for espera in (5, 15, 30, None):  # 429 (cota de 300 QPM) e 5xx transitorio: espera e tenta de novo
        r = requests.get(f"{API[api]}/{path.lstrip('/')}", params=params, timeout=30,
                         headers={"Authorization": f"Bearer {_token()}"})
        if not (r.status_code == 429 or r.status_code >= 500) or espera is None:
            break
        time.sleep(espera)
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            msg = r.text
        if soft:
            return {"_erro": f"HTTP {r.status_code}: {msg}"}
        sys.exit(f"HTTP {r.status_code} em {path}: {msg}")
    return r.json() if r.content else {}


def paginate(api, path, key, params=None, soft=False):
    params = dict(params or {})
    items = []
    while True:
        data = get(api, path, params, soft)
        if "_erro" in data:
            return data
        items += data.get(key, [])
        if not data.get("nextPageToken"):
            return items
        params["pageToken"] = data["nextPageToken"]
