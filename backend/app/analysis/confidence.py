"""Pewność wyniku (wysoka / średnia / ograniczona) i sekcja `reliability` kontraktu (SPEC 7.E).

Pewność liczona punktowo z jawnych przesłanek (start 100 pkt, odejmowanie za braki i uproszczenia),
progi: ≥ 75 wysoka, ≥ 50 średnia, < 50 ograniczona. Bez zdjęć satelitarnych lub analizy terenu
– najwyżej „średnia” (D36). Ograniczenia = przesłanki + ograniczenia z modułów + stałe.
Dane z przeterminowanego cache (źródło nie odpowiadało, D44) – pewność o jeden poziom niżej.
"""

from dataclasses import dataclass, field
from datetime import date

from app.analysis.soil import SoilAssessment
from app.analysis.water_balance import SoilWaterResult, WaterBalanceResult
from app.core.cache import StaleHit
from app.schemas.analysis import Completeness, Confidence, Reliability, SourceStatus

# ── PRZESŁANKI I PUNKTY (D36) ───────────────────────────────────────────────────────────────
PENALTY = {
    "pogoda_nasa": 10,  # siatka ~50 km
    "pogoda_zapasowa": 15,  # archiwum Open-Meteo zamiast NASA POWER
    "pogoda_opoznienie": 5,  # > 3 dni opóźnienia danych
    "pogoda_luka_scenariusz": 10,  # luka uzupełniona scenariuszem, nie danymi
    "et0_hargreaves": 10,  # > 10% dni sezonu metodą Hargreavesa
    "prognoza_brak": 10,  # data = dziś, a prognoza nie przyszła
    "data_historyczna": 5,  # ryzyko ze scenariusza typowej pogody
    "gleba_brak": 35,
    "gleba_punkty": 10,  # IUNG metodą zapasową (punkty)
    "gleba_czesciowo": 10,  # duża część działki poza mapą IUNG
    "gleba_nierolna_czesc": 5,  # < 80% gleb mineralnych użytków rolnych
    "satelita_brak": 15,
    "teren_brak": 10,
    "frakcje_brak": 5,  # brak SoilGrids – bez przepuszczalności i uziarnienia
}
LEVELS: list[tuple[int, Confidence]] = [(75, "wysoka"), (50, "srednia"), (0, "ograniczona")]
CONSTANT_LIMITATIONS = [
    "Model wody w glebie FAO-56 z parametrami tabelarycznymi upraw – nie uwzględnia odmiany, nawożenia "
    "ani poziomu wód gruntowych.",
    "Kategorie podatności IUNG opisują tylko gleby mineralne użytków rolnych.",
]


@dataclass
class Premise:
    key: str
    text: str
    points: int


@dataclass
class ConfidenceInputs:
    analysis_date: date
    today: date
    parcel_fetched: date
    weather_name: str | None  # None = brak pogody
    weather_resolution: str | None
    weather_fallback: bool
    weather_notes: list[str]
    weather_until: date | None
    forecast_ok: bool | None  # None = nie dotyczy (data historyczna)
    forecast_error: str | None
    soil: SoilAssessment
    model: SoilWaterResult | None
    wb: WaterBalanceResult | None
    hg_share_season: float | None
    satellite: bool = False
    terrain: bool = False
    extra_limitations: list[str] = field(default_factory=list)
    soilgrids: str | None = None  # "ok" | "brak" | None (nie pytano)
    soilgrids_error: str | None = None
    soil_map: str | None = None  # "ok" | "brak_konturu" | "brak" | None
    soil_map_error: str | None = None
    soil_map_year: int | None = None
    stale: list[StaleHit] = field(default_factory=list)


def premises(i: ConfidenceInputs) -> list[Premise]:
    out: list[Premise] = []

    def add(key: str, text: str) -> None:
        out.append(Premise(key, text, PENALTY[key]))

    if not i.satellite:
        add("satelita_brak", "brak zdjęć satelitarnych (kondycja roślin – w przygotowaniu)")
    if not i.terrain:
        add("teren_brak", "brak analizy terenu (spadki, spływ – w przygotowaniu)")
    if i.weather_name:
        if i.weather_fallback:
            add("pogoda_zapasowa", f"pogoda ze źródła zapasowego ({i.weather_name})")
        else:
            add("pogoda_nasa", f"pogoda uśredniona dla obszaru {i.weather_resolution}")
        if i.weather_until and (i.analysis_date - i.weather_until).days - 1 > 3:
            add("pogoda_opoznienie", f"dane pogodowe tylko do {i.weather_until:%d.%m.%Y}")
        if i.model and any("scenariuszem typowej pogody" in x for x in i.model.limitations):
            add("pogoda_luka_scenariusz", "ostatnie dni przed analizą uzupełnione scenariuszem typowej pogody")
        if i.hg_share_season is not None and i.hg_share_season > 0.10:
            add("et0_hargreaves", f"parowanie dla {round(100 * i.hg_share_season)}% dni liczone metodą uproszczoną")
    if i.forecast_ok is False:
        add("prognoza_brak", "brak prognozy pogody – ryzyko ze scenariusza typowej pogody")
    if i.forecast_ok is None and i.model and i.model.horizon_kind == "scenariusz":
        add("data_historyczna", "data historyczna – ryzyko na 7 dni ze scenariusza typowej pogody")
    if i.soilgrids == "brak":
        add("frakcje_brak", "brak frakcji gleby (SoilGrids)")
    if i.soil.method is None:
        add("gleba_brak", "brak danych o glebie (IUNG)")
    else:
        if i.soil.method == "punkty":
            add("gleba_punkty", "gleba sprawdzona w punktach (metoda zapasowa)")
        if any(s.name.startswith("IUNG") and s.status == "czesciowo" for s in i.soil.sources):
            add("gleba_czesciowo", "część działki poza mapą gleb IUNG")
        if i.soil.agricultural_share is not None and i.soil.agricultural_share < 0.8 and not i.soil.not_agricultural:
            add("gleba_nierolna_czesc", f"tylko {round(100 * i.soil.agricultural_share)}% działki to gleby rolne mineralne")
    return out


ORDER: list[Confidence] = ["wysoka", "srednia", "ograniczona"]


def level(points: int, capped: bool, stale: bool = False) -> Confidence:
    lv = next(name for t, name in LEVELS if points >= t)
    lv = "srednia" if capped and lv == "wysoka" else lv
    return ORDER[min(ORDER.index(lv) + 1, 2)] if stale else lv


def stale_text(h: StaleHit) -> str:
    local = h.stored_at.astimezone()
    return f"{h.source}: dane z cache z dnia {local:%d.%m.%Y %H:%M} (źródło nie odpowiadało)"


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def reliability(i: ConfidenceInputs) -> tuple[Reliability, list[Premise], int]:
    prem = premises(i)
    points = max(0, 100 - sum(p.points for p in prem))
    conf = level(points, capped=not (i.satellite and i.terrain), stale=bool(i.stale))
    top = sorted(prem, key=lambda p: -p.points)[:3]
    reason = ("Ograniczenia: " + "; ".join(p.text for p in top) + ".") if top else "Wszystkie źródła danych dostępne."
    if i.stale:
        reason = "Część danych z pamięci podręcznej (źródło nie odpowiadało) – pewność obniżona. " + reason

    sources: list[SourceStatus] = [
        SourceStatus(name="ULDK GUGiK", used_for="granice i powierzchnia działki", data_date=i.parcel_fetched, status="ok"),
    ]
    if i.weather_name:
        part = i.weather_fallback or any(p.key in ("pogoda_opoznienie", "et0_hargreaves") for p in prem)
        sources.append(SourceStatus(
            name=i.weather_name, used_for="pogoda z 10 lat, bilans wody, parowanie (ET0)", data_date=i.weather_until,
            resolution=i.weather_resolution, status="czesciowo" if part else "ok",
            note="źródło zapasowe" if i.weather_fallback else None,
        ))
    else:
        sources.append(SourceStatus(name="NASA POWER / Open-Meteo", used_for="pogoda z 10 lat", data_date=None, status="brak"))
    if i.forecast_ok is not None:
        sources.append(SourceStatus(
            name="Open-Meteo (prognoza)", used_for="ryzyko na 7 dni, plan nawadniania", data_date=i.today if i.forecast_ok else None,
            resolution="kilka km", status="ok" if i.forecast_ok else "brak", note=i.forecast_error,
        ))
    sources += i.soil.sources  # IUNG + EGiB (informacyjnie)
    if i.soilgrids is not None:
        sources.append(SourceStatus(
            name="SoilGrids (ISRIC)", used_for="frakcje gleby 0–30 cm, przepuszczalność", data_date=None,
            resolution="250 m", status="ok" if i.soilgrids == "ok" else "brak", note=i.soilgrids_error or "model globalny",
        ))
    if i.soil_map is not None:
        sources.append(SourceStatus(
            name="Mapa glebowo-rolnicza (GUGiK)", used_for="kompleks i gatunek gleby (informacyjnie)", data_date=None,
            resolution="1:5000", status="ok" if i.soil_map == "ok" else "brak",
            note=(f"mapa z ok. {i.soil_map_year} r." if i.soil_map_year else None) if i.soil_map == "ok" else
            (i.soil_map_error or "brak konturu w tym miejscu"),
        ))
    stale_by_source = {h.source: h for h in i.stale}
    sources = [
        s.model_copy(update={"status": "czesciowo", "note": stale_text(stale_by_source[s.name]).split(": ", 1)[1]})
        if s.name in stale_by_source else s for s in sources
    ]
    sources += [
        SourceStatus(name="Sentinel-2 L2A", used_for="kondycja i wilgotność roślin", data_date=None, resolution="10 m",
                     status="brak", note="w przygotowaniu"),
        SourceStatus(name="NMT GUGiK", used_for="teren i spływ wody", data_date=None, resolution="1 m",
                     status="brak", note="w przygotowaniu"),
        SourceStatus(name="BDOT10k", used_for="rowy, cieki i zbiorniki w okolicy", data_date=None,
                     status="brak", note="w przygotowaniu"),
    ]
    core = [s for s in sources if not s.name.startswith("EGiB") and not s.name.startswith("Mapa glebowo")]
    completeness = Completeness(available=sum(s.status != "brak" for s in core), total=len(core))

    lim = [stale_text(h) + "." for h in i.stale] + list(i.weather_notes)
    if i.weather_name and not i.weather_fallback:
        lim.insert(0, f"Pogoda uśredniona dla obszaru {i.weather_resolution} ({i.weather_name}).")
    if i.wb:
        lim += i.wb.limitations
    if i.model:
        lim += i.model.limitations
    lim += i.soil.limitations + i.extra_limitations
    if not i.satellite:
        lim.append("Brak zdjęć satelitarnych – kondycja i wilgotność roślin w przygotowaniu.")
    if not i.terrain:
        lim.append("Brak analizy terenu – spływ wody przyjęty w uproszczeniu (20% opadu powyżej 20 mm na dobę).")
    for c in CONSTANT_LIMITATIONS:  # bez powtórzeń treści już zgłoszonej przez moduły (np. gleba)
        if not ("gleby mineralne" in c and any("gleby mineralne" in x for x in lim)):
            lim.append(c)
    return Reliability(confidence=conf, reason=reason, sources=sources, completeness=completeness,
                       limitations=_dedupe(lim)), prem, points
