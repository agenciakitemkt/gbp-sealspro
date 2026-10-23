"""Formatacao para a tela (pt-BR). Sem acesso a banco nem rede."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scoring.engine import UNAVAILABLE, UNAVAILABLE_LEGACY

STATUS_LABEL = {"bad": "Fraco", "fair": "Razoável", "good": "Bom", "unavailable": "Indisponível",
                "not_applicable": "Não se aplica"}

_DAYS = [("MONDAY", "Seg"), ("TUESDAY", "Ter"), ("WEDNESDAY", "Qua"), ("THURSDAY", "Qui"),
         ("FRIDAY", "Sex"), ("SATURDAY", "Sáb"), ("SUNDAY", "Dom")]


try:
    _LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:  # sem banco de fusos: Brasilia sem horario de verao
    _LOCAL_TZ = timezone(timedelta(hours=-3))


def local_datetime(iso):
    """'2026-10-08T21:33:14+00:00' -> '08/10/2026 18:33' (Brasilia)."""
    return datetime.fromisoformat(iso).astimezone(_LOCAL_TZ).strftime("%d/%m/%Y %H:%M")


def local_short(iso):
    return datetime.fromisoformat(iso).astimezone(_LOCAL_TZ).strftime("%d/%m %H:%M")


def local_time(iso):
    return datetime.fromisoformat(iso).astimezone(_LOCAL_TZ).strftime("%H:%M")


def local_day(iso):
    return datetime.fromisoformat(iso).astimezone(_LOCAL_TZ).strftime("%d/%m/%Y")


def br_date(day):
    """'2026-09-30' -> '30/09/2026'; vazio vira '—'."""
    return datetime.fromisoformat(day).strftime("%d/%m/%Y") if day else "—"


def kind_label(kind):
    return {"real": "Real", "retroativa": "Retroativa"}.get(kind, kind)


def status_label(status):
    return STATUS_LABEL[status]


def render_message(message):
    """Template + variáveis -> texto. Decimais com vírgula.

    Análises guardadas antes da Fase 5a trazem o texto antigo de item indisponível (com o nome interno da seção):
    ele é trocado pelo atual na hora de exibir, sem mexer no que está no banco.
    """
    if message["template"] in UNAVAILABLE_LEGACY:
        return UNAVAILABLE
    vars_ = {k: (str(v).replace(".", ",") if isinstance(v, float) else v) for k, v in message["vars"].items()}
    return message["template"].format(**vars_)


def humanize_age(iso, now=None):
    """'há 3 dias', 'há 5 minutos'... para a linha 'Última atualização'."""
    now = now or datetime.now(timezone.utc)
    seconds = max(0, int((now - datetime.fromisoformat(iso)).total_seconds()))
    for size, one, many in ((86400, "dia", "dias"), (3600, "hora", "horas"), (60, "minuto", "minutos")):
        if seconds >= size:
            n = seconds // size
            return f"há {n} {one if n == 1 else many}"
    return "agora há pouco"


def band_position(score):
    """Posição do marcador (0-100%) numa barra de três faixas iguais: Fraco, Razoável, Bom."""
    if score >= 100:
        return 100.0
    if score < 50:
        return score / 50 * (100 / 3)
    return 100 / 3 + (score - 50) / 50 * (100 / 3)


def format_hours(hours):
    """{'MONDAY': [['07:00','16:00']], ...} -> [('Seg a Sex', '07:00–16:00'), ('Sáb e Dom', 'Fechado')]."""
    texts = [(label, ", ".join(f"{a}–{b}" for a, b in hours.get(key, [])) or "Fechado") for key, label in _DAYS]
    groups = []
    for label, text in texts:
        if groups and groups[-1][1] == text:
            groups[-1][0].append(label)
        else:
            groups.append(([label], text))
    out = []
    for labels, text in groups:
        name = labels[0] if len(labels) == 1 else f"{labels[0]} e {labels[1]}" if len(labels) == 2 \
            else f"{labels[0]} a {labels[-1]}"
        out.append((name, text))
    return out
