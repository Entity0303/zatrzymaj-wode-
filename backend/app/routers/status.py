"""GET /api/status – stan źródeł danych (zapytanie testowe, limit 5 s), wiek cache, rozgrzewka przykładów (B4).

Zapytania testowe omijają cache i są małe (jeden punkt, jeden dzień). Archiwum Open-Meteo nie jest
sprawdzane (dzienny limit zapytań na IP) – pokazujemy tylko jego cache.
A5d (D54, D55): źródło z otwartym bezpiecznikiem NIE jest odpytywane – „ograniczony (do HH:MM)”; blokada ULDK
wykryta zapytaniem testowym otwiera bezpiecznik ULDK (60 s). W trybie DEMO_OFFLINE nie ma zapytań testowych.
"""

import asyncio
import datetime as dt
from time import perf_counter

from fastapi import APIRouter

from app import demo
from app.core.cache import breaker, cache_stats, trip
from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, get_with_retry
from app.schemas.status import ServiceStatus, StatusResponse

router = APIRouter(prefix="/api", tags=["infrastruktura"])
PROBE_TIMEOUT_S = 5.0
# punkt testowy: działka 201305_2.0038.6/1 (podlaskie)
LON, LAT, E2180, N2180 = 22.6405, 52.8563, 741260.0, 582130.0


def _probes() -> list[tuple[str, str, str, dict | list, str]]:
    d, d2 = 0.0005, 10.0
    wms_pt = {"WIDTH": "101", "HEIGHT": "101", "I": "50", "J": "50", "STYLES": ""}
    return [
        ("ULDK GUGiK", "granice i powierzchnia działki", settings.uldk_url,
         {"request": "GetParcelById", "id": "201305_2.0038.6/1", "result": "id"}, "ULDK GUGiK"),
        ("NASA POWER", "pogoda z 10 lat (opad, temperatura, parowanie)", settings.nasa_power_url,
         {"parameters": "PRECTOTCORR", "community": "AG", "longitude": "22.6", "latitude": "52.9",
          "start": "20240101", "end": "20240101", "format": "JSON"}, "NASA POWER"),
        ("Open-Meteo", "prognoza pogody (ryzyko na 7 dni)", settings.open_meteo_forecast_url,
         {"latitude": f"{LAT:.2f}", "longitude": f"{LON:.2f}", "daily": "precipitation_sum", "forecast_days": "1"},
         "Open-Meteo"),
        ("IUNG-PIB", "kategoria gleby, ile wody zmieści gleba", settings.iung_wms_url,
         {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo", "LAYERS": settings.iung_soil_layer,
          "QUERY_LAYERS": settings.iung_soil_layer, "CRS": "EPSG:4326", "INFO_FORMAT": "application/json",
          "BBOX": f"{LAT - d},{LON - d},{LAT + d},{LON + d}", **wms_pt}, "IUNG-PIB"),
        ("KIEG / EGiB", "klasy bonitacyjne (informacyjnie)", settings.kieg_url,
         {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo", "LAYERS": "kontury",
          "QUERY_LAYERS": "kontury", "CRS": "EPSG:2180", "INFO_FORMAT": "text/html", "FORMAT": "image/png",
          "BBOX": f"{N2180 - d2},{E2180 - d2},{N2180 + d2},{E2180 + d2}", **wms_pt}, "KIEG / EGiB"),
        ("SoilGrids (ISRIC)", "frakcje gleby i przepuszczalność", settings.soilgrids_url,
         [("lon", f"{LON}"), ("lat", f"{LAT}"), ("property", "clay"), ("depth", "0-5cm"), ("value", "mean")],
         "SoilGrids (ISRIC)"),
        ("NMT GUGiK", "teren i spływ wody (wysokości)", settings.nmt_url,
         {"request": "GetHByPointList", "list": f"{N2180:.2f} {E2180:.2f}"}, "NMT GUGiK"),  # x = północ, y = wschód
        ("Mapa glebowo-rolnicza (GUGiK)", "kompleks i gatunek gleby (informacyjnie)", settings.soil_map_url,
         {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo", "LAYERS": "0", "QUERY_LAYERS": "0",
          "CRS": "EPSG:4326", "INFO_FORMAT": "text/xml", "BBOX": f"{LAT - d},{LON - d},{LAT + d},{LON + d}", **wms_pt},
         "Mapa glebowo-rolnicza (GUGiK)"),
    ]


def _limited(cache_name: str) -> str | None:
    b = breaker(cache_name)
    return f"ograniczony (do {b.until_local:%H:%M}) – {b.reason}" if b.open else None


async def _check(name: str, used_for: str, url: str, params, cache_name: str) -> ServiceStatus:
    t0 = perf_counter()
    ok, err = True, None
    n, age = cache_stats(cache_name)
    skip = ("tryb demo offline – bez zapytania testowego; dane tylko z cache" if settings.demo_offline
            else _limited(cache_name))
    if skip:
        return ServiceStatus(name=name, used_for=used_for, ok=bool(settings.demo_offline and n), response_ms=None,
                             error=skip, cache_entries=n, cache_newest_age_s=None if age is None else int(age))
    try:
        resp = await asyncio.wait_for(
            get_with_retry(url, params, source=name, timeout_s=PROBE_TIMEOUT_S, retries=0), PROBE_TIMEOUT_S + 0.5)
        # przekierowanie = RedirectBlocked (treści 3xx nie czytamy, D56); ULDK potrafi też odesłać stronę HTML
        html = name == "ULDK GUGiK" and resp.text[:300].lstrip().lower().startswith(("<!doctype", "<html"))
        if html:
            ok, err = False, "usługa chwilowo ogranicza ruch (przekierowanie)"
            if name == "ULDK GUGiK":  # D54: nie dokładamy zapytań do zablokowanego ULDK
                trip(cache_name, settings.uldk_breaker_s, err)
                err = _limited(cache_name)
        elif "ServiceException" in resp.text[:2000] or (name == "ULDK GUGiK" and resp.text.startswith("-1")):
            ok, err = False, "usługa zwróciła błąd zapytania testowego"
    except SourceError as exc:
        ok, err = False, exc.message
        if name == "ULDK GUGiK" and (isinstance(exc, RedirectBlocked) or "429" in exc.message):
            trip(cache_name, settings.uldk_breaker_s, exc.message)
            err = _limited(cache_name)
    except asyncio.TimeoutError:
        ok, err = False, f"brak odpowiedzi w {PROBE_TIMEOUT_S:.0f} s"
    except Exception as exc:  # noqa: BLE001 – /api/status nigdy nie zwraca 500 przez jedno źródło
        ok, err = False, f"nieoczekiwana odpowiedź usługi ({exc.__class__.__name__})"
    return ServiceStatus(name=name, used_for=used_for, ok=ok, response_ms=int((perf_counter() - t0) * 1000),
                         error=err, cache_entries=n, cache_newest_age_s=None if age is None else int(age))


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Czy źródła odpowiadają (zapytania testowe równolegle, limit 5 s), wiek cache, stan rozgrzewki przykładów."""
    services = list(await asyncio.gather(*(_check(*p) for p in _probes())))
    return StatusResponse(
        checked_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0),
        all_ok=all(s.ok for s in services),
        services=services,
        warmup_enabled=settings.demo_warmup,
        warmup=demo.warmup_state(),
    )
