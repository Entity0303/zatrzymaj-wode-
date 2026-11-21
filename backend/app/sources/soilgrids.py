"""ISRIC SoilGrids 2.0 (REST) – piasek, pył, ił i węgiel organiczny 0–30 cm w środku działki.

Zapytanie: /soilgrids/v2.0/properties/query?lon=&lat=&property=sand|silt|clay|soc&depth=0-5cm|5-15cm|15-30cm
&value=mean. Jednostki „mapped”: sand/silt/clay g/kg (d_factor 10 → %), soc dg/kg (d_factor 10 → g/kg).
Rozdzielczość 250 m (model globalny) – wartości orientacyjne. Licencja danych: CC BY 4.0 (ISRIC).
Źródło nie liczy niczego poza średnią ważoną po głębokości (5, 10, 15 cm).
"""

from dataclasses import dataclass

from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import SourceError, get_with_retry

SOURCE = "SoilGrids (ISRIC)"
SOURCE_URL = "https://soilgrids.org/"
RESOLUTION = "250 m"
DEPTHS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
PROPERTIES = ("sand", "silt", "clay", "soc")

_cache: TTLCache["SoilGridsResult"] = TTLCache(ttl_s=7 * 24 * 3600, max_items=512, name=SOURCE)


@dataclass(frozen=True)
class SoilGridsResult:
    sand_pct: float
    silt_pct: float
    clay_pct: float
    soc_g_kg: float | None  # węgiel organiczny, g/kg
    lon: float
    lat: float


def parse_response(payload: dict, lon: float, lat: float) -> SoilGridsResult:
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
        raise SourceError(SOURCE, "brak danych o glebie w tym miejscu (np. woda lub zabudowa)")
    # g/kg -> %; suma frakcji normalizowana do 100 (zaokrąglenia modelu)
    s, si, c = (out[k] / 10 for k in ("sand", "silt", "clay"))
    total = s + si + c
    if total <= 0:
        raise SourceError(SOURCE, "zerowe frakcje w odpowiedzi")
    return SoilGridsResult(
        sand_pct=round(100 * s / total, 1), silt_pct=round(100 * si / total, 1), clay_pct=round(100 * c / total, 1),
        soc_g_kg=None if out["soc"] is None else round(out["soc"], 1), lon=lon, lat=lat,
    )


async def texture_at(lon: float, lat: float) -> SoilGridsResult:
    """Frakcje 0–30 cm w punkcie. SourceError, gdy usługa nie odpowie (12 s) lub nie ma danych."""
    key = (round(lon, 4), round(lat, 4))

    async def download() -> SoilGridsResult:
        params = [("lon", f"{key[0]:.4f}"), ("lat", f"{key[1]:.4f}")]
        params += [("property", p) for p in PROPERTIES] + [("depth", d) for d in DEPTHS] + [("value", "mean")]
        resp = await get_with_retry(settings.soilgrids_url, params, source=SOURCE,
                                    timeout_s=settings.soilgrids_timeout_s, retries=0)
        try:
            payload = resp.json()
        except ValueError as exc:
            raise SourceError(SOURCE, "odpowiedź nie jest poprawnym JSON") from exc
        return parse_response(payload, *key)

    return await cached_fetch(_cache, key, SOURCE, download)


def clear_cache() -> None:
    _cache.clear()
