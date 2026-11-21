"""Sentinel-2 L2A – NDVI, NDMI, maska chmur SCL (CLAUDE.md, źródło 9).

Earth Search STAC https://earth-search.aws.element84.com/v1/search, kolekcja sentinel-2-l2a,
assety red, nir, swir16, scl (COG – odczyt fragmentów przez rasterio). Dane od 2017;
dla 2016 Copernicus Data Space STAC https://stac.dataspace.copernicus.eu/v1.

TODO (osoba A):
- najbliższe bezchmurne zdjęcie PRZED datą analizy (dla daty historycznej tylko wcześniejsze),
- NDVI/NDMI w obrysie (10 m), anomalia względem tych samych okresów z poprzednich lat,
- data zdjęcia do source_tag („Z satelity · data”).
"""

SOURCE = "Sentinel-2 L2A (Earth Search)"
