"""Widełki wyniku rankingu (A21, audyt V2): jak plon i ryzyko zmieniają się przy innych danych o opadach i glebie.

Warianty (każdy to pełny ranking `suggestions.build` – z pamięci wyniku, klucz obejmuje odcisk pogody i glebę):
- opad: gdy głównym źródłem są stacje IMGW – opad NASA × współczynnik działki; gdy główna jest NASA – opad ±10%,
- WOD: dolna i górna granica przedziału kategorii IUNG działki (kat. II 127,5–169,9 mm, III 170–202,5 mm);
  dla kat. I i IV (przedział otwarty) – ±20% wartości użytej w modelu.
Z wariantów i wyniku bazowego: plon typowy min–max, słaby rok min–max, lata ze stratą > 20% min–max.

Wydajność: warianty to 3–4 dodatkowe symulacje (14 upraw × 10 lat). Analiza czeka na nie najwyżej `wait_s`
(ustawienie `ranking_variants_wait_s`, domyślnie 1 s); gdy nie zdążą – liczą się dalej w tle, odpowiedź ma
`ranges_pending = true`, a następne zapytanie dostaje je z pamięci. Raport PDF czeka do końca.
"""

from __future__ import annotations

import asyncio
import dataclasses
from collections import OrderedDict
from datetime import date

import numpy as np

from app.analysis import suggestions as S
from app.analysis.et0 import DailyWeather
from app.schemas.analysis import CropSuggestions
from app.sources import iung

Ranges = dict[str, dict[str, tuple[float, float]]]  # crop_id → {"typ": (min, max), "weak": …, "risk": …}
_done: OrderedDict[tuple, Ranges] = OrderedDict()
_tasks: dict[tuple, asyncio.Future] = {}
MEMO_MAX = 64


def wod_bounds(category: int | None, wod_mm: float) -> tuple[float, float]:
    """(dolna, górna) granica WOD: przedział kategorii IUNG, a dla I / IV / nieznanej albo WOD spoza przedziału –
    ± `wod_open_pct` % wartości z modelu."""
    cfg = S.config()["variants"]
    pct = cfg["wod_open_pct"] / 100.0
    lo, hi = (iung.CODES.get(category or 0) or (None, None, None, None))[1:3]
    if lo is not None and hi is not None and lo <= wod_mm <= hi:
        return float(lo), float(hi)
    return round(wod_mm * (1 - pct), 1), round(wod_mm * (1 + pct), 1)


def specs(w: DailyWeather, raw_precip: np.ndarray | None, precip_main: str | None, factor: float | None,
          ctx: S.Context) -> list[tuple[str, DailyWeather, S.Context]]:
    """Lista wariantów (nazwa, pogoda, kontekst gleby) – bez wyniku bazowego."""
    cfg = S.config()["variants"]
    out: list[tuple[str, DailyWeather, S.Context]] = []
    if precip_main in ("imgw", "imgw_daleko") and raw_precip is not None and len(raw_precip) == len(w.precip):
        alt = np.asarray(raw_precip, dtype=float) * (factor if factor is not None else 1.0)
        alt = np.where(np.isnan(alt), w.precip, alt)  # brak NASA danego dnia – zostaje opad bazowy
        out.append(("opad_nasa", dataclasses.replace(w, precip=alt, source=f"{w.source} [wariant: opad NASA]"), ctx))
    else:
        d = cfg["precip_pct"] / 100.0
        for name, k in (("opad_minus", 1 - d), ("opad_plus", 1 + d)):
            out.append((name, dataclasses.replace(w, precip=w.precip * k, source=f"{w.source} [wariant: opad ×{k:.2f}]"), ctx))
    lo, hi = wod_bounds(ctx.category, ctx.wod_mm)
    for name, wod in (("wod_dolna", lo), ("wod_gorna", hi)):
        if abs(wod - ctx.wod_mm) >= 0.5:
            out.append((name, w, dataclasses.replace(ctx, wod_mm=wod)))
    return out


def ranges_from(base: CropSuggestions | None, others: list[CropSuggestions | None]) -> Ranges:
    """Min–max po wyniku bazowym i wariantach (bazowy zawsze w zakresie)."""
    def items(s: CropSuggestions | None) -> dict:
        return {} if s is None else {i.crop_id: i for g in s.groups for i in g.items}

    b = items(base)
    alt = [items(o) for o in others]
    out: Ranges = {}
    for cid, it in b.items():
        row = {}
        for key, attr in (("typ", "yield_typical_t_ha"), ("weak", "yield_weak_t_ha"), ("risk", "drought_risk_years")):
            vals = [getattr(it, attr)] + [getattr(a[cid], attr) for a in alt if cid in a]
            vals = [v for v in vals if v is not None]
            if vals:
                row[key] = (min(vals), max(vals))
        out[cid] = row
    return out


def _compute(w, raw_precip, precip_main, factor, analysis_date: date, ctx: S.Context, years: int) -> Ranges:
    base = S.build(w, analysis_date, ctx, years)
    others = [S.build(vw, analysis_date, vctx, years) for _n, vw, vctx in specs(w, raw_precip, precip_main, factor, ctx)]
    return ranges_from(base, others)


def _key(w: DailyWeather, raw_precip, precip_main, factor, analysis_date: date, ctx: S.Context, years: int) -> tuple:
    raw = "" if raw_precip is None else S.hashlib.blake2b(np.ascontiguousarray(raw_precip, dtype=float).tobytes(),
                                                           digest_size=8).hexdigest()
    return (S.weather_key(w), raw, precip_main, None if factor is None else round(factor, 3), analysis_date, years,
            repr(ctx), id(S.config()))


async def ranges(w: DailyWeather, raw_precip, precip_main: str | None, factor: float | None, analysis_date: date,
                 ctx: S.Context, years: int, wait_s: float | None) -> Ranges | None:
    """Zakresy z pamięci albo liczone w osobnym wątku. `wait_s` – ile najwyżej czekamy (None = do końca);
    None w wyniku = jeszcze się liczą (w tle), odpowiedź bez zakresów."""
    key = _key(w, raw_precip, precip_main, factor, analysis_date, ctx, years)
    if key in _done:
        _done.move_to_end(key)
        return _done[key]
    fut = _tasks.get(key)
    if fut is None or fut.done():
        fut = asyncio.ensure_future(asyncio.to_thread(_compute, w, raw_precip, precip_main, factor, analysis_date, ctx, years))
        _tasks[key] = fut

        def finish(f: asyncio.Future, key=key) -> None:
            _tasks.pop(key, None)
            if not f.cancelled() and f.exception() is None:
                _done[key] = f.result()
                while len(_done) > MEMO_MAX:
                    _done.popitem(last=False)

        fut.add_done_callback(finish)
    try:
        if wait_s is None:
            return await asyncio.shield(fut)
        return await asyncio.wait_for(asyncio.shield(fut), wait_s)
    except asyncio.TimeoutError:
        return None
    except Exception:  # noqa: BLE001 – warianty nie mogą wywrócić analizy
        return None


def clear() -> None:
    _done.clear()
    _tasks.clear()
