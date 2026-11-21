"""NMT GUGiK – wysokości terenu ±0,1 m (CLAUDE.md, źródło 7).

https://services.gugik.gov.pl/nmt/  request=GetHByPointList&list="x y,x y,..."
UWAGA: EPSG:2180 z kolejnością x = PÓŁNOC, y = WSCHÓD (odwrotnie niż ULDK!).
GET do ~400 punktów (dłuższy URL -> 414), POST z list=... max 1000 punktów (~2,5 s).

TODO (osoba A):
- siatka punktów w obrysie + bufor (POST w paczkach po 1000),
- zwrot macierzy wysokości do analysis/terrain.py.
"""

SOURCE = "NMT GUGiK"
