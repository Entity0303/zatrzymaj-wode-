"""Czas polski (A29). Serwer (kontener) działa w UTC, a rolnik w Polsce – „dziś” i godziny pokazywane w raporcie
liczymy w strefie Europe/Warsaw (z czasem letnim), nie w czasie serwera: po północy czasu polskiego domyślna data
analizy nie może być wczorajsza, a stopka PDF nie może pokazywać godziny o 1–2 h wcześniejszej.

Baza stref: systemowa (`/usr/share/zoneinfo` jest w obrazie `python:3.12-slim`); gdyby jej zabrakło – czas UTC
(nie wywracamy aplikacji) i ostrzeżenie w logu.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

log = logging.getLogger("uvicorn.error")
try:
    WARSAW: ZoneInfo | timezone = ZoneInfo("Europe/Warsaw")
except ZoneInfoNotFoundError:  # brak bazy stref w obrazie – wtedy `tzdata` w requirements
    WARSAW = timezone.utc
    log.warning("Brak bazy stref czasowych (Europe/Warsaw) – godziny i „dziś” w UTC")


def utcnow() -> datetime:
    """Bieżąca chwila (UTC, ze strefą). Jedno miejsce do podmiany w testach."""
    return datetime.now(timezone.utc)


def now_pl() -> datetime:
    """Teraz w czasie polskim."""
    return utcnow().astimezone(WARSAW)


def today_pl() -> date:
    """Dzisiejsza data w Polsce – domyślna data analizy."""
    return now_pl().date()


def to_pl(d: datetime) -> datetime:
    """Chwila `d` w czasie polskim; datę bez strefy traktujemy jako UTC (tak zapisuje ją serwer)."""
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(WARSAW)
