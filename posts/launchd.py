"""Agendador do macOS para o publicador (CLAUDE.md, secao 17).

Um LaunchAgent do usuario roda `coletar.py publicar` a cada LAUNCHD_INTERVAL_SECONDS. Com o Mac dormindo, o launchd
junta as execucoes perdidas e roda uma vez ao acordar; com o Mac desligado, roda ao entrar na conta (RunAtLoad).
"""

import os
import plistlib
import subprocess
import sys

from posts import config

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def plist_path():
    return os.path.expanduser(f"~/Library/LaunchAgents/{config.LAUNCHD_LABEL}.plist")


def plist_content(python=None, project=HERE):
    logs = os.path.join(project, "data", "logs")
    return {
        "Label": config.LAUNCHD_LABEL,
        "ProgramArguments": [python or os.path.join(project, ".venv", "bin", "python"),
                             os.path.join(project, "coletar.py"), "publicar"],
        "WorkingDirectory": project,
        "StartInterval": config.LAUNCHD_INTERVAL_SECONDS,
        "RunAtLoad": True,
        "StandardOutPath": os.path.join(logs, "publicador-launchd.log"),
        "StandardErrorPath": os.path.join(logs, "publicador-launchd.log"),
    }


def _domain():
    return f"gui/{os.getuid()}"


def install():
    path = plist_path()
    content = plist_content()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.makedirs(os.path.dirname(content["StandardOutPath"]), exist_ok=True)
    subprocess.run(["launchctl", "bootout", _domain(), path], capture_output=True)  # se ja existia, recarrega
    with open(path, "wb") as f:
        plistlib.dump(content, f)
    r = subprocess.run(["launchctl", "bootstrap", _domain(), path], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Não foi possível ligar o agendador: {r.stderr.strip() or r.returncode}")
    return path


def uninstall():
    path = plist_path()
    subprocess.run(["launchctl", "bootout", _domain(), path], capture_output=True)
    if os.path.exists(path):
        os.remove(path)
    return path


def installed():
    return os.path.isfile(plist_path())


def loaded():
    r = subprocess.run(["launchctl", "print", f"{_domain()}/{config.LAUNCHD_LABEL}"], capture_output=True)
    return r.returncode == 0
