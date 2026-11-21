"""Obszar przybliżony (A5b-2b, D69): analiza po punkcie, gdy granic działki nie da się pobrać z ULDK.

Kwadrat 100 × 100 m (1 ha) w EPSG:2180 wokół punktu – wyraźnie oznaczony w odpowiedzi (`approximate_area`), z niższą
pewnością. Województwo (potrzebne do plonów GUS w rankingu) – najbliższy środek województwa: bez granic administracyjnych
w repo, przy granicy województw może być sąsiednie (zapisane w nocie). Do indeksu znanych działek ULDK NIE trafia.
"""

from __future__ import annotations

import math

from shapely.geometry import box

from app.core.geo import lonlat_to_2180
from app.sources.uldk import Parcel

SIDE_M = 100.0
APPROX_PREFIX = "obszar_przyblizony"
NOTE = "Obszar przybliżony – brak dokładnych granic działki. Analiza dla kwadratu 1 ha wokół wskazanego punktu."
# przybliżone środki geometryczne województw (lon, lat)
VOIVODESHIP_CENTERS = {
    "dolnośląskie": (16.41, 51.09), "kujawsko-pomorskie": (18.49, 53.07), "lubelskie": (22.90, 51.22),
    "lubuskie": (15.34, 52.20), "łódzkie": (19.42, 51.60), "małopolskie": (20.27, 49.85),
    "mazowieckie": (21.10, 52.35), "opolskie": (17.85, 50.65), "podkarpackie": (22.17, 49.94),
    "podlaskie": (22.94, 53.27), "pomorskie": (17.98, 54.22), "śląskie": (18.99, 50.42),
    "świętokrzyskie": (20.76, 50.76), "warmińsko-mazurskie": (20.82, 53.86), "wielkopolskie": (17.23, 52.33),
    "zachodniopomorskie": (15.55, 53.59),
}


def nearest_voivodeship(lon: float, lat: float) -> str:
    k = math.cos(math.radians(lat))
    return min(VOIVODESHIP_CENTERS, key=lambda v: ((VOIVODESHIP_CENTERS[v][0] - lon) * k) ** 2
               + (VOIVODESHIP_CENTERS[v][1] - lat) ** 2)


def is_approximate(parcel_id: str) -> bool:
    return parcel_id.startswith(APPROX_PREFIX)


def approximate_parcel(lon: float, lat: float, side_m: float = SIDE_M) -> Parcel:
    e, n = lonlat_to_2180(lon, lat)
    h = side_m / 2
    woj = nearest_voivodeship(lon, lat)
    return Parcel(id=f"{APPROX_PREFIX}_{lat:.5f}_{lon:.5f}", voivodeship=woj, county="nieznany", commune="nieznana",
                  region="nieznany", number="—", geom_2180=box(e - h, n - h, e + h, n + h), source="approximate")
