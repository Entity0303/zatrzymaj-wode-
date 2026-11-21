"""Gleba dla rolnika (D41): uziarnienie, przepuszczalność, zachowanie wody przy ulewie, mapa glebowo-rolnicza.

- Klasa uziarnienia – trójkąt USDA (algorytm NRCS), nazwy po polsku. Uwaga: polska klasyfikacja PTG 2008
  dzieli piaski drobniej – gatunek z mapy glebowo-rolniczej (jeśli jest) ma pierwszeństwo w opisie.
- Ksat – Saxton i Rawls (2006), Soil Sci. Soc. Am. J. 70:1569–1578, równania 1–3, 5, 15–16
  (piasek, ił jako ułamek, materia organiczna % = 1,72 × węgiel organiczny %, przycięta do 8%).
- Woda z ulewy (progi D41): Ksat ≥ 50 mm/h – „ucieka” (szybko wsiąka i przesiąka w głąb),
  12–50 – „zatrzymuje”, < 12 – „splywa” (ryzyko spływu i zastoisk).
"""

import math

from app.core.http import SourceError
from app.schemas.analysis import Soil, SoilMapInfo, SoilPermeability, SoilTexture, SourceTag
from app.sources import soil_map as soil_map_src
from app.sources.soil_map import SoilMapResult
from app.sources.soilgrids import SoilGridsResult

USDA_PL = {
    "sand": "piasek", "loamy_sand": "piasek gliniasty", "sandy_loam": "glina piaszczysta", "loam": "glina",
    "silt_loam": "glina pylasta", "silt": "pył", "sandy_clay_loam": "glina piaszczysto-ilasta",
    "clay_loam": "glina ilasta", "silty_clay_loam": "glina pylasto-ilasta", "sandy_clay": "ił piaszczysty",
    "silty_clay": "ił pylasty", "clay": "ił",
}
KSAT_FAST, KSAT_SLOW = 50.0, 12.0
KSAT_LABELS = [(50, "bardzo duża"), (25, "duża"), (12, "średnia"), (4, "mała"), (0, "bardzo mała")]
RAIN_TEXT = {
    "ucieka": "Woda z ulewy szybko wsiąka, ale gleba mało jej zatrzymuje – przesiąka w głąb, poza zasięg korzeni.",
    "zatrzymuje": "Woda z ulewy dobrze wsiąka, a gleba zatrzymuje dużą jej część w zasięgu korzeni.",
    "splywa": "Woda z ulewy wsiąka powoli – część spływa po powierzchni albo stoi w zagłębieniach (zastoiska).",
}
METHOD = "Saxton i Rawls (2006), frakcje i węgiel organiczny z SoilGrids"


def usda_class(sand: float, silt: float, clay: float) -> str:
    """Klasa uziarnienia USDA (frakcje w %, suma ~100)."""
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 2 * clay < 30:
        return "loamy_sand"
    if (7 <= clay < 20 and sand > 52) or (clay < 7 and silt < 50):
        return "sandy_loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt_loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy_clay_loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay_loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty_clay_loam"
    if clay >= 35 and sand > 45:
        return "sandy_clay"
    if clay >= 40 and silt >= 40:
        return "silty_clay"
    return "clay"


def ksat_saxton_rawls(sand_pct: float, clay_pct: float, organic_carbon_pct: float | None) -> float:
    """Przewodnictwo wodne w stanie nasycenia, mm/h."""
    S, C = sand_pct / 100, clay_pct / 100
    OM = min(8.0, max(0.0, 1.72 * (organic_carbon_pct if organic_carbon_pct is not None else 1.0)))
    t1500t = -0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM + 0.068 * S * C + 0.031
    t1500 = t1500t + (0.14 * t1500t - 0.02)
    t33t = -0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM + 0.452 * S * C + 0.299
    t33 = t33t + (1.283 * t33t**2 - 0.374 * t33t - 0.015)
    ts33t = 0.278 * S + 0.034 * C + 0.022 * OM - 0.018 * S * OM - 0.027 * C * OM - 0.584 * S * C + 0.078
    ts33 = ts33t + (0.636 * ts33t - 0.107)
    ts = t33 + ts33 - 0.097 * S + 0.043
    B = (math.log(1500) - math.log(33)) / (math.log(t33) - math.log(t1500))
    lam = 1 / B
    return max(0.0, 1930 * max(ts - t33, 0.0) ** (3 - lam))


def rain_retention(ksat: float) -> str:
    if ksat >= KSAT_FAST:
        return "ucieka"
    return "zatrzymuje" if ksat >= KSAT_SLOW else "splywa"


def ksat_label(ksat: float) -> str:
    return next(name for t, name in KSAT_LABELS if ksat >= t)


def texture(sg: SoilGridsResult) -> SoilTexture:
    code = usda_class(sg.sand_pct, sg.silt_pct, sg.clay_pct)
    return SoilTexture(
        sand_pct=sg.sand_pct, silt_pct=sg.silt_pct, clay_pct=sg.clay_pct,
        organic_carbon_pct=None if sg.soc_g_kg is None else round(sg.soc_g_kg / 10, 2),
        texture_class=USDA_PL[code], texture_code=code, depth="0–30 cm",
        source_tag=SourceTag(kind="szacunek_modelu", source="SoilGrids (ISRIC), 250 m"),
    )


def permeability(t: SoilTexture) -> SoilPermeability:
    k = ksat_saxton_rawls(t.sand_pct, t.clay_pct, t.organic_carbon_pct)
    ret = rain_retention(k)
    return SoilPermeability(
        ksat_mm_h=round(k) if k >= 10 else round(k, 1), label=ksat_label(k), rain_retention=ret, description=RAIN_TEXT[ret], method=METHOD,
        source_tag=SourceTag(kind="obliczenia", source="SoilGrids + Saxton i Rawls (2006)"),
    )


def soil_map_info(m: SoilMapResult) -> SoilMapInfo:
    deeper = [soil_map_src.label(c) or c for c in m.layers[1:]]
    return SoilMapInfo(
        complex_code=m.complex_code, complex_label=m.complex_label, species_code=m.species_code,
        species_label=m.species_label, deeper=deeper, soil_type_code=m.soil_type_code, mapped_year=m.mapped_year,
        source_tag=SourceTag(kind="pomiar", source="Mapa glebowo-rolnicza 1:5000 (GUGiK)"),
    )


def enrich_soil(
    soil: Soil,
    sg: SoilGridsResult | SourceError | None,
    sm: SoilMapResult | SourceError | None,
) -> tuple[Soil, list[str]]:
    """Dokłada do sekcji `soil` frakcje, przepuszczalność i mapę glebowo-rolniczą. Zwraca też ograniczenia."""
    notes, lim = [], []
    tex = perm = smi = None
    if isinstance(sg, SoilGridsResult):
        tex = texture(sg)
        perm = permeability(tex)
        lim.append("Frakcje gleby i przepuszczalność z modelu globalnego SoilGrids (250 m) – wartości orientacyjne, "
                   "nie pomiar na tej działce.")
    elif isinstance(sg, SourceError):
        notes.append(f"Frakcje gleby: brak danych ({sg.message}).")
    else:
        notes.append("Frakcje gleby: SoilGrids nie ma danych w tym miejscu (np. woda, zabudowa).")
    if isinstance(sm, SoilMapResult):
        smi = soil_map_info(sm)
        if sm.mapped_year:
            lim.append(f"Mapa glebowo-rolnicza opracowana ok. {sm.mapped_year} r. – stan gleby mógł się zmienić.")
    elif isinstance(sm, SourceError):
        notes.append(f"Mapa glebowo-rolnicza: brak danych ({sm.message}).")
    elif sm is None:
        notes.append("Mapa glebowo-rolnicza: brak konturu w tym miejscu.")
    upd = {"texture": tex, "permeability": perm, "soil_map": smi, "texture_note": " ".join(notes) or None}
    return soil.model_copy(update=upd), lim
