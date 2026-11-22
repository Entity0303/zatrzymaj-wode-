"""„Wody gruntowe i zapas z opadów” (A27) – obliczenia. Część B: ile opadu zostaje w glebie – z naszych danych (opad
i parowanie z 30 i 60 dni przed datą analizy, kategoria gleby IUNG, średni spadek terenu); połączenie z częścią A
(PIG-PIB: obszary zagrożone podtopieniami). Progi i teksty: `rules/groundwater.yaml`. Bez AI, bez nowych zapytań.

Wskaźnik mówi, ile wody z opadu zostaje w glebie dla roślin – to nie szybkość przesiąkania (A27c: dawniej „wsiąkanie”;
nazwy pól kontraktu – `infiltration` – zostały).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from app.schemas.groundwater import FloodZone, GroundwaterContext, Infiltration, SourcePig

RULES = Path(__file__).parent / "rules" / "groundwater.yaml"
SOIL_CODES = (1, 2, 3, 4, 5)
UNAVAILABLE_NOTE = "Nie udało się policzyć, ile opadu zostaje w glebie, ani sprawdzić danych PIG-PIB – spróbuj ponownie za chwilę."


@lru_cache
def cfg() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))["groundwater"]


def _mm(v: float) -> str:
    return f"{v:.0f}"


def window_sums(dates: np.ndarray, precip: np.ndarray, et0: np.ndarray, analysis_date: date, days: int,
                min_valid: float) -> tuple[float, float, date] | None:
    """Suma opadu i parowania z `days` dni kończących się dzień PRZED datą analizy. None – za mało ważnych dni."""
    end = np.datetime64(analysis_date, "D")
    start = end - np.timedelta64(days, "D")
    m = (dates >= start) & (dates < end)
    if not m.any():
        return None
    p, e = precip[m].astype(float), et0[m].astype(float)
    ok = ~np.isnan(p) & ~np.isnan(e)
    if ok.sum() < min_valid * days:
        return None
    last = dates[m][ok][-1].astype("datetime64[D]").astype(object)
    return float(np.nansum(p[ok])), float(np.nansum(e[ok])), last


def dominant_soil(shares: dict[int, float] | None) -> int | None:
    """Dominująca kategoria rolnicza (1–5) z udziałów kodów IUNG; brak gruntów rolnych → None."""
    agri = {int(k): v for k, v in (shares or {}).items() if int(k) in SOIL_CODES and v > 0}
    return max(agri, key=agri.get) if agri else None


def infiltration(dates: np.ndarray, precip: np.ndarray, et0: np.ndarray, analysis_date: date,
                 soil_code: int | None = None, slope_mean_pct: float | None = None) -> Infiltration | None:
    """Ile opadu zostaje w glebie (poziom) i zdanie dla rolnika. None – brak danych pogodowych z ostatnich 30 dni."""
    c = cfg()
    w30 = window_sums(dates, precip, et0, analysis_date, 30, c["min_valid_share"])
    if w30 is None:
        return None
    w60 = window_sums(dates, precip, et0, analysis_date, 60, c["min_valid_share"])
    cap = float(c["ratio_cap"])

    def ratio(p: float, e: float) -> float:
        return cap if e < 1.0 else min(cap, p / e)

    r = ratio(w30[0], w30[1])
    if w60 is not None:
        r = c["weight_30d"] * r + (1 - c["weight_30d"]) * ratio(w60[0], w60[1])
    key = soil_code if soil_code in SOIL_CODES else "unknown"
    index = r * float(c["soil_retention"][key])
    steep = False
    if slope_mean_pct is not None:
        s = c["slope"]
        if slope_mean_pct >= s["steep_pct"]:
            index, steep = index * s["steep_factor"], True
        elif slope_mean_pct >= s["moderate_pct"]:
            index, steep = index * s["moderate_factor"], True
    lv = c["levels"]
    level = "dobre" if index >= lv["dobre_min"] else "slabe" if index >= lv["slabe_min"] else "bardzo_slabe"
    tail_key = "bardzo_slabe_heavy" if level == "bardzo_slabe" and key in (3, 4, 5) else level
    light = key in c["light_soil_codes"] and level in c["light_soil_note_levels"]
    sentence = c["sentence_light" if light else "sentence"].format(
        soil=c["soil_words"][key], p30=_mm(w30[0]), e30=_mm(w30[1]), tail=c["tails"][tail_key])
    if light:
        sentence += c["light_soil_note"]
    if steep:
        sentence += c["slope_note"].format(s=f"{slope_mean_pct:.0f}")
    label = c["labels"][level]
    return Infiltration(
        level=level, label_pl=label, sentence_pl=sentence,
        short_pl=c["short"].format(label=label, p30=_mm(w30[0]), e30=_mm(w30[1])),
        precip_30d_mm=round(w30[0], 1), et0_30d_mm=round(w30[1], 1),
        precip_60d_mm=round(w60[0], 1) if w60 else None, et0_60d_mm=round(w60[1], 1) if w60 else None,
        soil_code=soil_code if soil_code in SOIL_CODES else None,
        slope_mean_pct=round(slope_mean_pct, 1) if slope_mean_pct is not None else None,
        index=round(index, 2), data_until=w30[2])


def combine(inf: Infiltration | None, zone, pig_failed: bool, wet_hollow_pct: float | None,
            analysis_date: date, depth_note: str, pig_unavailable_note: str) -> GroundwaterContext:
    """Składa wynik: zapas z opadów (B) + obszar podtopień PIG-PIB (A). `zone` – `sources.pig.FloodZone` albo None."""
    c = cfg()
    if inf is None and (pig_failed or zone is None):
        return GroundwaterContext(unavailable=True, note_pl=UNAVAILABLE_NOTE, analysis_date=analysis_date,
                                  source_pig=SourcePig(unavailable=True, note_pl=pig_unavailable_note))
    flood = None
    interpretation = None
    after_rain = may_reduce = False
    if zone is not None and not pig_failed:
        t = c["interpretation"]
        if zone.in_zone:
            may_reduce = True
            if wet_hollow_pct is not None and wet_hollow_pct >= c["wet_hollow_min_pct"]:
                after_rain = True
                interpretation = t["flood_and_hollow"].format(hollow=f"{wet_hollow_pct:.0f}")
            else:
                interpretation = t["flood_zone"]
            interpretation += t["may_reduce_drought"]
            flood = FloodZone(in_zone=True, label_pl="obszar zagrożony podtopieniami", water_region=zone.water_region)
        else:
            interpretation = t["no_flood_zone"]
            flood = FloodZone(in_zone=False, label_pl="poza obszarem zagrożonym podtopieniami")
    return GroundwaterContext(
        infiltration=inf, flood_zone=flood, depth_m=None,
        source_pig=SourcePig(unavailable=pig_failed or zone is None,
                             note_pl=pig_unavailable_note if pig_failed or zone is None else depth_note),
        flood_after_rain=after_rain, may_reduce_drought=may_reduce, interpretation_pl=interpretation,
        fetched_at=datetime.now(timezone.utc).replace(microsecond=0), analysis_date=analysis_date)
