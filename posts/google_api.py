"""Chamadas ao Google para publicar postagens. E o UNICO arquivo do projeto que escreve no Google (teste trava isso:
tests/test_posts.py). Tudo pela API v4 legada (localPosts e media), com o login do gbp_auth (business.manage).

Achados da Fase 0 (CLAUDE.md, 17.2): a imagem da postagem precisa de link (sourceUrl); o arquivo vai antes para a
galeria do perfil (startUpload + bytes + media.create) e o link definitivo so aparece depois que o Google processa a
foto (o primeiro, /gpu-csl/, da erro 500 na postagem).
"""

import requests

import gbp_auth

V4 = "https://mybusiness.googleapis.com/v4"
UPLOAD = "https://mybusiness.googleapis.com/upload/v1/media"
TIMEOUT = 60
PROVISIONAL_URL_MARK = "/gpu-csl/"  # link provisorio da foto recem-enviada (hipotese: so este formato e provisorio)


class GoogleError(Exception):
    """Erro de uma chamada. retryable: vale tentar de novo mais tarde (rede, 429, 5xx)."""

    def __init__(self, message, status=None, retryable=False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class TokenError(GoogleError):
    """O login do Google nao funciona mais (token revogado ou vencido): so o usuario resolve, com fase0.py login."""

    def __init__(self, message="O login do Google precisa ser refeito."):
        super().__init__(message, retryable=True)


def _token():
    try:
        return gbp_auth._token()
    except SystemExit as e:  # gbp_auth encerra o programa quando falta configuracao
        raise TokenError(str(e)) from None
    except Exception as e:  # RefreshError (invalid_grant) e afins
        raise TokenError(f"O login do Google precisa ser refeito ({type(e).__name__}).") from None


def _message(r):
    try:
        err = r.json().get("error", {})
        details = [d.get("message") for x in err.get("details", []) for d in x.get("errorDetails", [])]
        return "; ".join(filter(None, [err.get("message")] + details)) or r.text[:300]
    except ValueError:
        return r.text[:300]


class GoogleClient:
    """Cliente real. Os testes usam um falso com os mesmos metodos."""

    def __init__(self, session=None):
        self.http = session or requests.Session()

    def _call(self, method, url, **kw):
        headers = {"Authorization": f"Bearer {_token()}", **kw.pop("headers", {})}
        try:
            r = self.http.request(method, url, headers=headers, timeout=TIMEOUT, **kw)
        except requests.RequestException as e:
            raise GoogleError(f"Sem conexão com o Google ({type(e).__name__}).", retryable=True) from None
        if r.status_code == 401:
            raise TokenError()
        if r.status_code >= 400:
            raise GoogleError(f"Google respondeu {r.status_code}: {_message(r)}", status=r.status_code,
                              retryable=r.status_code == 429 or r.status_code >= 500)
        return r.json() if r.content else {}

    def upload_photo(self, account_id, location_id, jpeg_bytes):
        """Sobe a foto para a galeria do perfil (categoria ADDITIONAL). Devolve o item de midia criado."""
        base = f"{V4}/{account_id}/{location_id}/media"
        ref = self._call("POST", f"{base}:startUpload", json={})["resourceName"]
        self._call("POST", f"{UPLOAD}/{ref}", params={"upload_type": "media"}, data=jpeg_bytes,
                   headers={"Content-Type": "image/jpeg"})
        return self._call("POST", base, json={"mediaFormat": "PHOTO", "dataRef": {"resourceName": ref},
                                              "locationAssociation": {"category": "ADDITIONAL"}})

    def get_media(self, media_name):
        return self._call("GET", f"{V4}/{media_name}")

    def create_post(self, account_id, location_id, body):
        return self._call("POST", f"{V4}/{account_id}/{location_id}/localPosts", json=body)

    def get_post(self, post_name):
        return self._call("GET", f"{V4}/{post_name}")

    def recent_posts(self, account_id, location_id):
        return self._call("GET", f"{V4}/{account_id}/{location_id}/localPosts",
                          params={"pageSize": 20}).get("localPosts", [])


def definitive_url(media):
    """Link da foto que serve para a postagem, ou None enquanto o Google ainda processa."""
    url = (media or {}).get("googleUrl") or ""
    return url if url.startswith("https://") and PROVISIONAL_URL_MARK not in url else None
