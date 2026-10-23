"""Montagem da tela de postagens (calendario, rotulos, alerta da ultima postagem). Sem rede; so le o banco e o bruto."""

import calendar
from datetime import date, datetime, timedelta, timezone

import storage
from posts import config
from posts.publisher import iso, parse
from scoring import config as scoring_config
from web.format import _LOCAL_TZ

WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]

# status -> (rotulo, classe de cor). "Nova tentativa" = agendada que ja teve tentativa com erro.
STATUS = {
    "agendada": ("Agendada", "agendada"),
    "nova tentativa": ("Nova tentativa", "tentativa"),
    "publicando": ("Publicando", "agendada"),
    "publicada": ("Publicada", "publicada"),
    "recusada": ("Recusada", "falhou"),
    "falhou": ("Falhou", "falhou"),
    "atrasada": ("Atrasada", "tentativa"),
}
EDITABLE = {"agendada", "atrasada", "falhou"}
DELETABLE = {"agendada", "atrasada", "falhou", "recusada"}


def display_status(post):
    if post["status"] == "agendada" and post["attempts"]:
        return "nova tentativa"
    return post["status"]


def local(iso_utc):
    return datetime.fromisoformat(iso_utc).astimezone(_LOCAL_TZ)


def local_to_utc(value):
    """'2026-10-19T09:45' (horario de Brasilia, do campo da tela) -> ISO UTC. ValueError se invalido."""
    dt = datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M")
    return iso(dt.replace(tzinfo=_LOCAL_TZ))


def month_bounds(year, month):
    """Inicio e fim do mes em UTC (ISO), pela hora de Brasilia."""
    start = datetime(year, month, 1, tzinfo=_LOCAL_TZ)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=_LOCAL_TZ)
    return iso(start), iso(end)


def parse_month(value, today):
    try:
        y, m = (int(x) for x in (value or "").split("-"))
        if 2000 <= y <= 2100 and 1 <= m <= 12:
            return y, m
    except ValueError:
        pass
    return today.year, today.month


def shift_month(year, month, delta):
    n = year * 12 + month - 1 + delta
    return n // 12, n % 12 + 1


def calendar_weeks(year, month, posts, today):
    """Semanas (domingo a sabado) com as postagens de cada dia, pela hora de Brasilia."""
    by_day = {}
    for p in posts:
        by_day.setdefault(local(p["scheduled_at"]).date(), []).append(p)
    weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year, month):
        weeks.append([{"date": d, "in_month": d.month == month, "today": d == today, "past": d < today,
                       "posts": by_day.get(d, [])} for d in week])
    return weeks


def _raw_last_post(location_id):
    """Data da postagem mais recente vista na ultima coleta da Completa (inclui as feitas fora do app)."""
    raw = storage.latest_raw(location_id)
    dates = [p.get("createTime") for p in (raw or {}).get("localPosts") or [] if isinstance(p, dict)]
    dates = [d for d in dates if isinstance(d, str)]
    return datetime.fromisoformat(max(dates).replace("Z", "+00:00")) if dates else None


def last_post_alert(db, location_id, now):
    """Situacao do item 'Data da ultima postagem' (29) da Completa: ultima publicada, proxima agendada e, se for o
    caso, a data em que o perfil passa do limite sem postagem."""
    limit_days = scoring_config.CONFIG["last_post"]["steps"][0][0]
    posts = storage.list_posts(db, location_id)
    published = [parse(p["published_at"]) for p in posts if p["status"] == "publicada" and p["published_at"]]
    raw_last = _raw_last_post(location_id)
    last = max([d for d in published + [raw_last] if d], default=None)
    upcoming = sorted(parse(p["scheduled_at"]) for p in posts
                      if p["status"] in ("agendada", "publicando") and parse(p["scheduled_at"]) >= now - timedelta(hours=1))
    nxt = upcoming[0] if upcoming else None
    deadline = last + timedelta(days=limit_days) if last else None
    out = {"limit": limit_days, "last": last, "last_days": (now - last).days if last else None, "next": nxt,
           "deadline": deadline, "level": None}
    if last is None:
        out["level"] = "sem_postagem" if nxt is None else None
    elif deadline <= now:
        out["level"] = "vencido" if nxt is None or nxt > now + timedelta(days=1) else None
    elif nxt is None or nxt > deadline:
        out["level"] = "vai_vencer"
    return out


def today_local(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(_LOCAL_TZ).date()


def default_when(day=None, now=None):
    """Valor inicial do campo de data e hora: o dia clicado as 09:00 ou amanha as 09:00."""
    d = day or (today_local(now) + timedelta(days=1))
    return f"{d.isoformat()}T{config.DEFAULT_HOUR}"


def parse_day(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None
