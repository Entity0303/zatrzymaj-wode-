"""Ceny skupu i przychód z pola (A12, D99).

Źródło: GUS BDL, temat P2967 (ceny skupu ważniejszych produktów rolnych, średnia roczna, zł/dt) – pobrane raz
`scripts/build_prices.py` do app/data/prices/gus_prices.csv (analiza nie pyta GUS w czasie działania).
Cena do przychodu: średnia z 3 ostatnich dostępnych lat dla województwa działki; brak w województwie → średnia
krajowa z dopiskiem. Rzepak i buraki cukrowe – w BDL tylko do 2018 r. (temat P1458) → bez ceny (revenue = null).
Przychód: typowy plon (t/ha) × powierzchnia uprawy × cena, zaokrąglony do 100 zł; słaby rok – analogicznie.
„Cena teraz” (ZSRIR MRiRW): tylko gdy jest plik prices_zsrir_latest.csv (przepisany ręcznie z biuletynu) – bez zgadywania.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.schemas.analysis import CropRevenue, CropSuggestions, PriceNow

DATA = Path(__file__).parents[1] / "data" / "prices"
REPO = Path(__file__).parents[3]
ZSRIR_FILES = (DATA / "prices_zsrir_latest.csv", REPO / "research" / "prices" / "prices_zsrir_latest.csv")
YEARS = 3
# produkt GUS → uprawy z rankingu (crops.csv)
PRODUCT_CROPS = {
    "pszenica": ["pszenica_ozima", "zboza_ozime"], "żyto": ["zyto"],
    "jęczmień": ["jeczmien_ozimy", "jeczmien_jary", "zboza_jare"], "owies": ["owies"],
    "pszenżyto": ["pszenzyto_ozime"], "kukurydza": ["kukurydza_ziarno"], "ziemniaki": ["ziemniak"],
}
CROP_PRODUCT = {c: p for p, cs in PRODUCT_CROPS.items() for c in cs}


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[str, dict[int, float]]]:
    """produkt → jednostka (nazwa województwa / „polska”) → rok → zł/t."""
    out: dict = defaultdict(lambda: defaultdict(dict))
    try:
        with open(DATA / "gus_prices.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                unit = "polska" if r["poziom"] == "polska" else r["nazwa"].strip().lower()
                out[r["produkt"]][unit][int(r["rok"])] = float(r["zl_dt"]) * 10.0  # zł/dt → zł/t
    except FileNotFoundError:
        return {}
    return {p: dict(u) for p, u in out.items()}


def price(crop_id: str, voivodeship: str | None) -> tuple[float, str] | None:
    """(zł/t, opis źródła) – średnia z 3 ostatnich lat dla województwa, inaczej średnia krajowa; brak → None."""
    prod = CROP_PRODUCT.get(crop_id)
    units = _table().get(prod or "", {})
    woj = (voivodeship or "").strip().lower().replace("województwo ", "")
    for unit, label in ((woj, f"woj. {woj}"), ("polska", "Polska")):
        by_year = units.get(unit)
        if not by_year:
            continue
        ys = sorted(by_year)[-YEARS:]
        val = sum(by_year[y] for y in ys) / len(ys)
        span = f"{ys[0]}–{ys[-1]}" if len(ys) > 1 else f"{ys[0]}"
        src = f"GUS – ceny skupu, {label}, {span}"
        if unit == "polska" and woj:
            src += f" (brak danych dla woj. {woj})"
        return round(val), src
    return None


def _round100(x: float) -> float:
    return float(round(x, -2))


def revenue(crop_id: str, typical_t_ha: float | None, weak_t_ha: float | None, area_ha: float | None,
            voivodeship: str | None) -> CropRevenue | None:
    p = price(crop_id, voivodeship)
    if p is None or typical_t_ha is None or not area_ha:
        return None
    zl_t, src = p
    weak = weak_t_ha if weak_t_ha is not None else typical_t_ha
    return CropRevenue(price_zl_t=zl_t, price_source=src, typical_zl=_round100(typical_t_ha * area_ha * zl_t),
                       weak_year_zl=_round100(weak * area_ha * zl_t), for_area_ha=round(area_ha, 2))


def attach(sug: CropSuggestions | None, voivodeship: str | None) -> CropSuggestions | None:
    """Przychód dla każdej uprawy rankingu, wyboru rolnika i lepszych możliwości (plony z rankingu)."""
    if sug is None:
        return None
    area = sug.area.value_ha if sug.area else None
    yields: dict[str, tuple[float | None, float | None]] = {}
    groups = []
    for g in sug.groups:
        items = []
        for it in g.items:
            yields[it.crop_id] = (it.yield_typical_t_ha, it.yield_weak_t_ha)
            items.append(it.model_copy(update={"revenue": revenue(it.crop_id, it.yield_typical_t_ha,
                                                                  it.yield_weak_t_ha, area, voivodeship)}))
        groups.append(g.model_copy(update={"items": items}))

    def rev(crop_id: str) -> CropRevenue | None:
        ty, wk = yields.get(crop_id, (None, None))
        return revenue(crop_id, ty, wk, area, voivodeship)

    choice = [c.model_copy(update={"revenue": rev(c.crop_id)}) for c in sug.choice]
    alts = [a.model_copy(update={"revenue": rev(a.crop_id)}) for a in sug.alternatives]
    return sug.model_copy(update={"groups": groups, "choice": choice, "alternatives": alts})


def price_now() -> list[PriceNow] | None:
    """Bieżące ceny ZSRIR – tylko z ręcznie przepisanego pliku (kolumny: crop_id, zl_t, week, url); brak → None."""
    for f in ZSRIR_FILES:
        if not f.exists():
            continue
        out = []
        with open(f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    out.append(PriceNow(crop_id=r["crop_id"], zl_t=float(r["zl_t"]), week=r["week"],
                                        source="ZSRIR MRiRW", url=r.get("url") or None))
                except (KeyError, ValueError):
                    continue
        return out or None
    return None


def clear() -> None:
    _table.cache_clear()
