"""ISRIC SoilGrids 2.0 (REST) – piasek, pył, ił i węgiel organiczny 0–30 cm w środku działki.

Zapytanie: /soilgrids/v2.0/properties/query?lon=&lat=&property=sand|silt|clay|soc&depth=0-5cm|5-15cm|15-30cm
&value=mean. Jednostki „mapped”: sand/silt/clay g/kg (d_factor 10 → %), soc dg/kg (d_factor 10 → g/kg).
Rozdzielczość 250 m (model globalny) – wartości orientacyjne. Licencja danych: CC BY 4.0 (ISRIC).
Źródło nie liczy niczego poza średnią ważoną po głębokości (5, 10, 15 cm).
"""

import asyncio
from dataclasses import dataclass

from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import SourceError, get_with_retry

SOURCE = "SoilGrids (ISRIC)"
SOURCE_URL = "https://soilgrids.org/"
RESOLUTION = "250 m"
DEPTHS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
PROPERTIES = ("sand", "silt", "clay", "soc")

_cache: TTLCache["SoilGridsResult"] = TTLCache(ttl_s=None, max_items=512, name=SOURCE)


@dataclass(frozen=True)
class SoilGridsResult:
    sand_pct: float
    silt_pct: float
    clay_pct: float
    soc_g_kg: float | None  # węgiel organiczny, g/kg
    lon: float
    lat: float


def parse_response(payload: dict, lon: float, lat: float) -> "SoilGridsResult | None":
    """None = SoilGrids nie ma danych w tym miejscu (woda, zabudowa) – poprawna odpowiedź, nie awaria."""
    try:
        layers = {l["name"]: l for l in payload["properties"]["layers"]}
    except (KeyError, TypeError) as exc:
        raise SourceError(SOURCE, "nieoczekiwany format odpowiedzi") from exc
    out: dict[str, float | None] = {}
    for prop in PROPERTIES:
        layer = layers.get(prop)
        if not layer:
            out[prop] = None
            continue
        factor = float(layer.get("unit_measure", {}).get("d_factor", 10) or 10)
        num = den = 0.0
        for d in layer.get("depths", []):
            w = DEPTHS.get(d.get("label"))
            v = (d.get("values") or {}).get("mean")
            if w and v is not None:
                num += w * float(v) / factor
                den += w
        out[prop] = num / den if den else None
    if out["sand"] is None or out["silt"] is None or out["clay"] is None:
        return None
    # g/kg -> %; suma frakcji normalizowana do 100 (zaokrąglenia modelu)
    s, si, c = (out[k] / 10 for k in ("sand", "silt", "clay"))
    total = s + si + c
    if total <= 0:
        return None
    return SoilGridsResult(
        sand_pct=round(100 * s / total, 1), silt_pct=round(100 * si / total, 1), clay_pct=round(100 * c / total, 1),
        soc_g_kg=None if out["soc"] is None else round(out["soc"], 1), lon=lon, lat=lat,
    )


async def texture_at(lon: float, lat: float) -> "SoilGridsResult | None":
    """Frakcje 0–30 cm w punkcie. SourceError, gdy usługa nie odpowie (12 s) lub nie ma danych."""
    key = (round(lon, 4), round(lat, 4))

    async def download() -> "SoilGridsResult | None":
        params = [("lon", f"{key[0]:.4f}"), ("lat", f"{key[1]:.4f}")]
        params += [("property", p) for p in PROPERTIES] + [("depth", d) for d in DEPTHS] + [("value", "mean")]
        resp = await get_with_retry(settings.soilgrids_url, params, source=SOURCE,
                                    timeout_s=settings.soilgrids_timeout_s, retries=0)
        try:
            payload = resp.json()
        except ValueError as exc:
            raise SourceError(SOURCE, "odpowiedź nie jest poprawnym JSON") from exc
        return parse_response(payload, *key)

    return await cached_fetch(_cache, key, SOURCE, download, timeout_s=settings.soilgrids_timeout_s,
                              breaker_s=300)


# A22: analiza czeka na SoilGrids najwyżej `soilgrids_wait_s` (5 s); wolniejsza odpowiedź dociąga się w tle
# (do `soilgrids_timeout_s`) i trafia do cache – kolejne zapytanie o tę działkę ma ją od razu (jak teren i satelita)
PENDING_MESSAGE = "odpowiada wolno – dociągane w tle, będzie przy kolejnym przeliczeniu"
_tasks: dict[tuple, asyncio.Future] = {}


async def texture_budget(lon: float, lat: float, wait_s: float | None = None,
                         must_wait: bool = False) -> "SoilGridsResult | None":
    """Jak `texture_at`, ale czekamy najwyżej `wait_s`; po tym czasie SourceError(PENDING_MESSAGE), a pobieranie
    trwa dalej w tle (wynik w cache). A23: pobieranie idzie wspólną kolejką zadań w tle jako ostatnie – gdy czeka
    w kolejce, od razu PENDING (analiza nie czeka); `must_wait` – czekaj mimo kolejki (brak innych danych o glebie)."""
    wait_s = settings.soilgrids_wait_s if wait_s is None else wait_s
    key = (round(lon, 4), round(lat, 4))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    task = _tasks.get(key)
    queued = False
    if task is None or task.done():
        from app.core import background

        queued = background.busy("soilgrids")  # A23: SoilGrids startuje ostatni – analiza nie czeka na kolejkę
        task = asyncio.ensure_future(background.run("soilgrids", f"{key[0]},{key[1]}", texture_at(lon, lat)))
        _tasks[key] = task

        def finish(t: asyncio.Future, key=key) -> None:
            _tasks.pop(key, None)
            if not t.cancelled():
                t.exception()  # błąd odebrany – bez ostrzeżenia „exception was never retrieved”

        task.add_done_callback(finish)
    if queued and not must_wait:
        raise SourceError(SOURCE, PENDING_MESSAGE)
    try:
        return await asyncio.wait_for(asyncio.shield(task), wait_s)
    except asyncio.TimeoutError as exc:
        raise SourceError(SOURCE, PENDING_MESSAGE) from exc


def clear_cache() -> None:
    _cache.clear()
    _tasks.clear()
