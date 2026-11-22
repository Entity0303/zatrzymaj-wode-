"""Europejskie Obserwatorium Suszy (EDO / GDO, Copernicus Emergency Management Service, JRC) – tło suszowe (A26).

WMS: https://drought.emergency.copernicus.eu/api/wms (WMS 1.1.1; sprawdzone 22.11.2026). Warstwy dekadowe (TIME =
pierwszy dzień dekady: 1, 11 albo 21 dnia miesiąca):
- `cdiad` – Combined Drought Indicator v4.1 (od 2012 r.): Watch / Warning / Alert,
- `cdirc` – uzupełnienie CDI: „Normal, no drought” i trzy klasy regeneracji,
- `smian` – anomalia wskaźnika wilgotności gleby (SMI Anomaly, od 1995 r.),
- `rdria` – Risk of Drought Impact for Agriculture (od 2010 r.): Low / Medium / High.
Usługa NIE obsługuje GetFeatureInfo („Invalid request type”), więc wartość w punkcie odczytujemy z koloru środkowego
piksela GetMap 3×3 px i mapujemy po legendzie (GetLegendGraphic – kolory poniżej odczytane z legend 22.11.2026).
Uwaga: obraz 1×1 px usługa zwraca zawsze przezroczysty (sprawdzone) – stąd 3×3. Dekada spoza zakresu warstwy
(np. najnowsza, jeszcze nieopublikowana) = HTTP 400 z kodem `InvalidDimensionValue` – to nie awaria, tylko brak danych
dla tej dekady (zwracamy piksel przezroczysty, żeby wziąć wcześniejszą dekadę).

Warunki korzystania (https://drought.emergency.copernicus.eu/terms&conditions): informacje usług Copernicus są
udostępniane bezpłatnie, w pełni i otwarcie na podstawie rozporządzenia (UE) 2021/696, bez gwarancji; GetCapabilities:
Fees „no fees”, AccessConstraints „no constraints”. Podajemy źródło: Copernicus European Drought Observatory (EDO), JRC.
"""

from __future__ import annotations

import io
from datetime import date

import httpx

from app.core.cache import TTLCache, cached_fetch
from app.core.http import RedirectBlocked, SourceError, request

SOURCE = "Copernicus EDO"
SOURCE_LABEL = "Copernicus European Drought Observatory (EDO), JRC"
SOURCE_URL = "https://drought.emergency.copernicus.eu/"
WMS_URL = "https://drought.emergency.copernicus.eu/api/wms"
TIMEOUT_S = 8.0
TTL_TODAY_S = 24 * 3600.0
TTL_HISTORY_S = 30 * 86400.0
_cache: TTLCache[tuple] = TTLCache(ttl_s=TTL_TODAY_S, max_items=2048, name=SOURCE)

# kolor piksela (R, G, B) → klasa; przezroczysty piksel = brak klasy w tej warstwie
CDI = {(240, 228, 66): "obserwacja", (230, 159, 0): "ostrzeżenie", (220, 5, 12): "alarm"}
CDI_RECOVERY = {(255, 255, 255): "brak", (204, 121, 167): "regeneracja", (0, 158, 115): "regeneracja",
                (202, 178, 214): "regeneracja"}
# anomalia wilgotności gleby: (środek przedziału do pola `value`, klucz)
SMA = {(179, 88, 6): (-2.5, "bardzo_sucho"), (241, 163, 64): (-1.75, "bardzo_sucho"), (254, 224, 182): (-1.25, "sucho"),
       (255, 255, 255): (0.0, "w_normie"), (209, 229, 240): (1.25, "wilgotno"), (103, 169, 207): (1.75, "wilgotno"),
       (33, 102, 172): (2.5, "wilgotno")}
SMA_NO_DATA = (200, 200, 200)
AGRI_RISK = {(255, 255, 0): "niskie", (255, 205, 0): "srednie", (255, 0, 0): "wysokie"}
MAX_COLOR_DIST = 40  # tolerancja dopasowania koloru (wygładzanie krawędzi w PNG)
PX = 3  # bok obrazu GetMap; 1 px usługa zwraca pusty
NO_DATA = (0, 0, 0, 0)  # przezroczysty piksel: brak klasy / brak danych dla dekady


def nearest(rgb: tuple[int, int, int], table: dict) -> object | None:
    """Klasa o najbliższym kolorze (odległość euklidesowa ≤ MAX_COLOR_DIST), inaczej None."""
    best, best_d = None, None
    for color, value in table.items():
        d = sum((a - b) ** 2 for a, b in zip(rgb, color)) ** 0.5
        if best_d is None or d < best_d:
            best, best_d = value, d
    return best if best_d is not None and best_d <= MAX_COLOR_DIST else None


def decode_pixel(png: bytes) -> tuple[int, int, int, int]:
    """PNG → (R, G, B, A) środkowego piksela."""
    from PIL import Image  # Pillow jest w obrazie (zależność WeasyPrint)

    try:
        with Image.open(io.BytesIO(png)) as im:
            return tuple(im.convert("RGBA").getpixel((im.width // 2, im.height // 2)))  # type: ignore[return-value]
    except Exception as exc:  # noqa: BLE001 – nie-obraz (komunikat błędu usługi)
        raise SourceError(SOURCE, "odpowiedź nie jest obrazem PNG") from exc


async def pixel(layer: str, lon: float, lat: float, time: date, today: date | None = None) -> tuple[int, int, int, int]:
    """Kolor piksela warstwy w punkcie dla dekady `time` (GetMap 3×3 px, bbox ok. 2 km wokół punktu). Cache: 24 h dla
    dekad z ostatnich 30 dni, 30 dni dla starszych."""
    key = (layer, round(lon, 2), round(lat, 2), time.isoformat())
    recent = (today or date.today()) - time
    ttl = TTL_TODAY_S if recent.days <= 30 else TTL_HISTORY_S

    async def download() -> tuple[int, int, int, int]:
        d = 0.01
        params = {"SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap", "LAYERS": layer, "STYLES": "",
                  "SRS": "EPSG:4326", "BBOX": f"{lon - d:.4f},{lat - d:.4f},{lon + d:.4f},{lat + d:.4f}",
                  "WIDTH": str(PX), "HEIGHT": str(PX), "FORMAT": "image/png", "TRANSPARENT": "TRUE", "TIME": time.isoformat()}
        try:
            resp = await request("GET", WMS_URL, source=SOURCE, timeout_s=TIMEOUT_S, params=params, max_bytes=200_000)
        except RedirectBlocked as exc:
            raise SourceError(SOURCE, exc.message) from exc
        except httpx.TimeoutException as exc:
            raise SourceError(SOURCE, f"usługa nie odpowiada (przekroczono {TIMEOUT_S:.0f} s)") from exc
        except httpx.TransportError as exc:
            raise SourceError(SOURCE, f"brak połączenia z usługą ({exc.__class__.__name__})") from exc
        if resp.status_code == 400 and b"InvalidDimensionValue" in resp.content[:2000]:
            return NO_DATA  # dekada spoza zakresu warstwy (jeszcze nieopublikowana albo sprzed początku serii)
        if resp.status_code != 200:
            raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
        return decode_pixel(resp.content)

    return await cached_fetch(_cache, key, SOURCE, download, ttl_s=ttl, breaker_s=120, breaker_after=3,
                              breaker_window_s=60)


def clear_cache() -> None:
    _cache.clear()
