"""BDOT10k – rowy, cieki, kanały, wody powierzchniowe (CLAUDE.md, źródło 8).

WMS: https://mapy.geoportal.gov.pl/wss/service/pub/guest/kompozycja_BDOT10k_WMS/MapServer/WMSServer
Warstwy: row, rz, kan, rzOk, kanOkr, WPow. GetMap PNG wokół działki (0,3–1,5 s) -> odległość
do najbliższego obiektu; GetFeatureInfo INFO_FORMAT=text/xml -> x_kod (SWRS rzeka/strumień,
SWRM rów melioracyjny) i data aktualizacji.

TODO (osoba A): najbliższy rów/ciek/zbiornik z odległością i typem; obiekty do warstwy „Spływ wody”.
"""

SOURCE = "BDOT10k GUGiK"
