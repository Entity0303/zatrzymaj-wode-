"""Mapa glebowo-rolnicza 1:5000 (PZGiK, GUGiK) – usługa WMS Geoportalu, GetFeatureInfo w środku działki.

Sprawdzone na żywo 2026-11-21 (D43): warstwa „0” (KONTURY_GLEBOWE), INFO_FORMAT=text/xml (odpowiedź ESRI:
<FIELDS KOMPLEKS="2" TYPPODTYP="Bw" PODLOZE1="glp" … AKTUALNOSC="01.01.1973"/>). Kompleks przydatności
rolniczej, typ gleby i gatunek (uziarnienie) kolejnych warstw – PODLOZE1 = warstwa wierzchnia.
Punkt poza zasięgiem mapy → pusta odpowiedź (None, nie błąd). Mapy z lat 1960–1980 – informacja dodatkowa.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import SourceError, get_with_retry

SOURCE = "Mapa glebowo-rolnicza (GUGiK)"
SOURCE_URL = "https://www.geoportal.gov.pl/"
_NULL = {"", "Null", "null", "missing", ":", "."}

# Kompleksy przydatności rolniczej (grunty orne 1–14, użytki zielone 1z–3z)
COMPLEXES = {
    "1": "pszenny bardzo dobry", "2": "pszenny dobry", "3": "pszenny wadliwy", "4": "żytni bardzo dobry",
    "5": "żytni dobry", "6": "żytni słaby", "7": "żytni bardzo słaby", "8": "zbożowo-pastewny mocny",
    "9": "zbożowo-pastewny słaby", "10": "pszenny górski", "11": "zbożowy górski",
    "12": "owsiano-ziemniaczany górski", "13": "owsiano-pastewny górski",
    "14": "grunty orne przeznaczone pod użytki zielone",
    "1z": "użytki zielone bardzo dobre i dobre", "2z": "użytki zielone średnie", "3z": "użytki zielone słabe i bardzo słabe",
}
# Gatunki (uziarnienie) gleb mineralnych na mapie glebowo-rolniczej
SPECIES = {
    "pl": "piasek luźny", "plp": "piasek luźny pylasty", "ps": "piasek słabogliniasty",
    "psp": "piasek słabogliniasty pylasty", "pgl": "piasek gliniasty lekki", "pglp": "piasek gliniasty lekki pylasty",
    "pgm": "piasek gliniasty mocny", "pgmp": "piasek gliniasty mocny pylasty", "gl": "glina lekka",
    "glp": "glina lekka pylasta", "gs": "glina średnia", "gsp": "glina średnia pylasta", "gc": "glina ciężka",
    "gcp": "glina ciężka pylasta", "płz": "pył zwykły", "płi": "pył ilasty", "i": "ił", "ip": "ił pylasty",
    "l": "less", "li": "less ilasty", "ż": "żwir", "żp": "żwir piaszczysty", "żg": "żwir gliniasty",
}
# Gatunki piaszczyste – gleba przepuszczalna, mało wody (gruboziarnistość piasku)
SANDY = {"pl", "plp", "ps", "psp", "ż", "żp"}

_cache: TTLCache["SoilMapResult | None"] = TTLCache(ttl_s=7 * 24 * 3600, max_items=512, name=SOURCE)


@dataclass(frozen=True)
class SoilMapResult:
    complex_code: str | None
    soil_type_code: str | None
    layers: tuple[str, ...] = field(default_factory=tuple)  # kody PODLOZE1..5 (bez pustych)
    mapped_year: int | None = None

    @property
    def complex_label(self) -> str | None:
        return COMPLEXES.get(self.complex_code or "")

    @property
    def species_code(self) -> str | None:
        return self.layers[0] if self.layers else None

    @property
    def species_label(self) -> str | None:
        return label(self.species_code)


def label(code: str | None) -> str | None:
    if not code:
        return None
    return SPECIES.get(code) or SPECIES.get(code.lower())


def _val(attrs: dict, key: str) -> str | None:
    v = (attrs.get(key) or "").strip()
    return None if v in _NULL else v


def parse_response(text: str) -> "SoilMapResult | None":
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError as exc:
        raise SourceError(SOURCE, "odpowiedź nie jest poprawnym XML") from exc
    if root.tag.endswith("ServiceExceptionReport"):
        raise SourceError(SOURCE, "usługa zwróciła błąd zapytania")
    for f in root.iter():
        if not f.tag.endswith("FIELDS") or "KOMPLEKS" not in f.attrib:
            continue
        a = f.attrib
        layers = tuple(v for k in ("PODLOZE1", "PODLOZE2", "PODLOZE3", "PODLOZE4", "PODLOZE5") if (v := _val(a, k)))
        year = None
        m = re.search(r"(19|20)\d\d", a.get("AKTUALNOSC_NR") or a.get("AKTUALNOSC") or "")
        if m:
            year = int(m.group(0))
        else:
            m = re.search(r"z lat (\d{4})", a.get("UWAGI") or "")
            year = int(m.group(1)) if m else None
        return SoilMapResult(_val(a, "KOMPLEKS"), _val(a, "TYPPODTYP"), layers, year)
    return None  # punkt poza zasięgiem mapy


async def soil_map_at(lon: float, lat: float) -> "SoilMapResult | None":
    """Kontur mapy glebowo-rolniczej w punkcie (EPSG:4326). None = brak mapy w tym miejscu."""
    key = (round(lon, 5), round(lat, 5))

    async def download() -> "SoilMapResult | None":
        d = 0.0005
        params = {
            "SERVICE": "WMS", "REQUEST": "GetFeatureInfo", "VERSION": "1.3.0", "CRS": "EPSG:4326",
            "BBOX": f"{lat - d},{lon - d},{lat + d},{lon + d}",  # WMS 1.3.0 + EPSG:4326 = lat,lon
            "WIDTH": "101", "HEIGHT": "101", "I": "50", "J": "50", "LAYERS": "0", "QUERY_LAYERS": "0",
            "INFO_FORMAT": "text/xml", "FEATURE_COUNT": "5", "STYLES": "",
        }
        resp = await get_with_retry(settings.soil_map_url, params, source=SOURCE,
                                    timeout_s=settings.soil_map_timeout_s, retries=0)
        return parse_response(resp.text)

    return await cached_fetch(_cache, key, SOURCE, download, timeout_s=7.5)


def clear_cache() -> None:
    _cache.clear()
