"""Gerador de PDF: HTML -> PDF com o Chrome em modo headless, tudo local. Isolado nesta funcao para poder trocar o motor."""

import os
import shutil
import signal
import subprocess
import tempfile
import threading

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


LOCK = threading.Lock()  # um PDF por vez no app (cada um abre um Chrome), da Completa ou da Pre


class PdfError(Exception):
    """Falha ao gerar o PDF (Chrome ausente, tempo esgotado...). A mensagem pode ser mostrada ao usuario."""


def find_chrome():
    """Caminho do Chrome: variavel GBP_CHROME, instalacoes comuns do macOS ou o PATH. None se nao houver."""
    explicit = os.environ.get("GBP_CHROME")
    if explicit and os.path.isfile(explicit):
        return explicit
    for path in CHROME_CANDIDATES:
        if os.path.isfile(path):
            return path
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _is_complete_pdf(path):
    """Cabecalho %PDF no inicio e %%EOF no fim: arquivo inteiro, mesmo que o Chrome nao tenha encerrado."""
    if not os.path.isfile(path) or os.path.getsize(path) < 100:
        return False
    with open(path, "rb") as f:
        head = f.read(5)
        f.seek(-64, os.SEEK_END)
        tail = f.read()
    return head == b"%PDF-" and b"%%EOF" in tail


def html_to_pdf(html, out_path, timeout=90):
    """Converte uma pagina HTML (string) em PDF em `out_path`. O HTML so pode referenciar arquivos locais (file://)."""
    chrome = find_chrome()
    if chrome is None:
        raise PdfError("O Chrome não foi encontrado. Instale o Google Chrome ou defina GBP_CHROME com o caminho dele.")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gbp-relatorio-") as tmp:
        page = os.path.join(tmp, "relatorio.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(html)
        pdf_tmp = os.path.join(tmp, "relatorio.pdf")
        cmd = [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
               "--disable-extensions", "--disable-component-update", "--disable-background-networking",
               "--disable-sync", f"--print-to-pdf={pdf_tmp}", f"file://{page}"]
        # Nao usar --user-data-dir: com um perfil novo o Chrome grava o PDF mas nao encerra o processo (macOS).
        # Grupo de processos proprio: se estourar o tempo, mata o Chrome e seus auxiliares, nao so o processo principal.
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        if not _is_complete_pdf(pdf_tmp):
            raise PdfError("O Chrome demorou demais para gerar o PDF." if timed_out else "O Chrome não gerou o PDF.")
        shutil.move(pdf_tmp, out_path)
    return out_path
