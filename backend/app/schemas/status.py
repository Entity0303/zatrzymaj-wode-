"""GET /api/status – czy źródła danych odpowiadają, czas odpowiedzi, wiek cache, stan rozgrzewki przykładów."""

import datetime as dt
from typing import Literal

from pydantic import Field

from app.schemas.analysis import Contract

WarmupState = Literal["wylaczona", "oczekuje", "w_toku", "gotowe", "blad"]


class ServiceStatus(Contract):
    name: str = Field(description="Np. 'NASA POWER'")
    used_for: str
    ok: bool = Field(description="Czy zapytanie testowe się udało (limit 5 s)")
    response_ms: int | None = Field(None, description="Czas odpowiedzi zapytania testowego")
    error: str | None = None
    cache_entries: int = Field(0, description="Ile wyników tego źródła jest w pamięci podręcznej")
    cache_newest_age_s: int | None = Field(None, description="Wiek najnowszego wpisu w cache, s (null = pusty)")


class WarmupItem(Contract):
    id: str
    title: str
    state: WarmupState
    duration_ms: int | None = None
    finished_at: dt.datetime | None = None
    error: str | None = None


class StatusResponse(Contract):
    checked_at: dt.datetime
    all_ok: bool
    services: list[ServiceStatus]
    warmup_enabled: bool
    warmup: list[WarmupItem]
