import json
import logging
import re
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

log = logging.getLogger("uvicorn.error")
DEFAULT_CORS_ORIGIN_REGEX = r"^https://.*\.vercel\.app$"


def parse_origins(value: Any) -> list[str]:
    """A19: CORS_ORIGINS jako lista JSON (`["https://a", "https://b"]`) albo tekst z przecinkami (`https://a,https://b`);
    pusty = brak. Błędna wartość NIE wywraca startu – ostrzeżenie w logu i pusta lista."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = list(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("{"):
            log.warning("CORS_ORIGINS: oczekiwano listy, nie obiektu JSON (%r) – brak dozwolonych adresów", text[:200])
            return []
        if text.startswith("["):
            try:
                items = json.loads(text)
            except ValueError:
                log.warning("CORS_ORIGINS: niepoprawna lista JSON (%r) – brak dozwolonych adresów", text[:200])
                return []
            if not isinstance(items, list):
                log.warning("CORS_ORIGINS: JSON nie jest listą (%r) – brak dozwolonych adresów", text[:200])
                return []
        else:
            items = text.split(",")
    else:
        log.warning("CORS_ORIGINS: nieobsługiwany typ %s – brak dozwolonych adresów", type(value).__name__)
        return []
    out = [str(x).strip().strip("\"'").rstrip("/") for x in items if isinstance(x, str) and str(x).strip()]
    bad = [x for x in out if not x.startswith(("http://", "https://"))]
    if bad:
        log.warning("CORS_ORIGINS: pomijam wartości, które nie są adresem http(s): %r", bad[:5])
    return [x for x in out if x and x not in bad]


class Settings(BaseSettings):
    """Konfiguracja aplikacji (zmienne środowiskowe lub plik .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _origins(cls, v: Any) -> list[str]:
        return parse_origins(v)

    @field_validator("cors_origin_regex", mode="before")
    @classmethod
    def _origin_regex(cls, v: Any) -> str:
        """Błędne wyrażenie nie wywraca startu (CORSMiddleware kompiluje je przy starcie) – ostrzeżenie i brak regexu."""
        text = (v or "").strip() if isinstance(v, str) else ""
        if not text:
            return ""
        try:
            re.compile(text)
        except re.error as exc:
            log.warning("CORS_ORIGIN_REGEX: niepoprawne wyrażenie %r (%s) – pomijam", text[:200], exc)
            return ""
        return text

    http_timeout_s: float = 20.0
    http_ipv4_only: bool = True  # A23: klient HTTP łączy się tylko po IPv4 (błędne odpowiedzi DNS AAAA dla NMT GUGiK)
    user_agent: str = "Wodoskop/0.1 (HackNation 2026)"  # uczciwy User-Agent dla wszystkich źródeł (A6)
    # A19: JSON albo tekst z przecinkami (NoDecode – pydantic-settings nie dekoduje JSON-a sam, robi to parse_origins)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    # A13/A19: podglądy Vercela mają zmienne adresy; domyślnie każdy *.vercel.app (pusty napis = wyłączone)
    cors_origin_regex: str = DEFAULT_CORS_ORIGIN_REGEX
    # A13: gotowy cache w obrazie (app/data/seed/cache_seed.sqlite.gz) – wczytywany, gdy trwały cache jest pusty
    cache_seed: bool = True

    uldk_url: str = "https://uldk.gugik.gov.pl/"
    uldk_timeout_s: float = 10.0
    iung_wms_url: str = "https://sgeo.iung.pl/geoserver/Susza/wms"
    iung_wcs_url: str = "https://sgeo.iung.pl/geoserver/Susza/wcs"
    iung_soil_layer: str = "Susza:katgl_landuse2024"
    iung_coverage_id: str = "Susza__katgl_landuse2024"
    iung_timeout_s: float = 8.0
    # powyżej tylu komórek 5 m prosimy WCS o mniejszą rozdzielczość (SCALEFACTOR)
    iung_wcs_max_cells: int = 250_000
    kieg_url: str = "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow"
    kieg_timeout_s: float = 8.0
    nasa_power_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    # na próbę; przy 1 ponownej próbie + zapasowym Open-Meteo całość mieści się w limicie 30 s
    nasa_power_timeout_s: float = 9.0
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    open_meteo_archive_timeout_s: float = 10.0
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"

    # ile punktów w obrysie działki sprawdza zapasowa metoda IUNG (GetFeatureInfo)
    soil_sample_points: int = 16
    # ile lat wstecz pobieramy dane pogodowe
    history_years: int = 10

    # cache (D53): trwały plik SQLite (pusty = tylko pamięć procesu, np. testy); w Dockerze w wolumenie /data
    cache_db: str = ""
    # pogoda z ostatnich 7 dni (NASA uzupełnia je z opóźnieniem) – 6 h; dni zakończone wcześniej – bez wygasania
    cache_ttl_current_s: float = 6 * 3600
    cache_ttl_forecast_s: float = 3600
    # tryb demo offline (D55): żadnych zapytań zewnętrznych, tylko cache – na prezentację
    demo_offline: bool = False
    # A8 (D89): źródła wyłączone pojedynczo – tylko cache (GUGiK blokuje sieć); reszta (IMGW, Earth Search, NASA, IUNG,
    # SoilGrids, prognoza Open-Meteo) działa normalnie. Klucze: uldk, nmt, kieg, uug, bdot, prng, soil_map, ortho.
    # Pusty napis = wszystkie źródła włączone. Domyślnie (A18) tylko BDOT10k – GUGiK na żywo; w sieci, która blokuje
    # GUGiK: OFFLINE_SOURCES="uldk,nmt,kieg,uug,bdot".
    offline_sources: str = "bdot"
    # A8 (D89): usługi GUGiK (nazwa źródła zawiera „GUGiK”) – wspólny limit: najwyżej tyle zapytań naraz i odstęp
    # między startami kolejnych zapytań; bezpiecznik (cached_fetch) jak dotąd
    gugik_parallel: int = 2
    gugik_min_interval_s: float = 0.5
    # działki demo z app/data/demo_parcels.json ładowane do indeksu działek przy starcie (D54)
    demo_parcels_preload: bool = True
    # ULDK: blokada (302 / 429 / HTML) – ponowienia po 1 s i 3 s, potem bezpiecznik na 60 s (D54)
    uldk_retry_delays_s: list[float] = [1.0, 3.0]
    # A21: ile najwyżej analiza czeka na widełki rankingu (warianty opadu i gleby); dłużej – liczą się w tle
    ranking_variants: bool = True
    ranking_variants_wait_s: float = 1.0
    uldk_breaker_s: float = 30.0  # P1: próbne zamknięcie po 30 s (było 60 s po pierwszym błędzie)
    uldk_breaker_failures: int = 5  # P1: bezpiecznik ULDK dopiero po tylu błędach …
    uldk_breaker_window_s: float = 60.0  # … w tym oknie
    uldk_retry_timeout_s: float = 15.0  # P1: po przekroczeniu czasu jedno ponowienie z dłuższym limitem

    soilgrids_url: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    soilgrids_timeout_s: float = 12.0
    soilgrids_wait_s: float = 5.0  # A22: tyle czeka analiza; wolniejsza odpowiedź dociąga się w tle do cache
    soil_map_url: str = "https://mapy.geoportal.gov.pl/wss/service/pub/guest/MapaGlebowoRolnicza/MapServer/WMSServer"
    soil_map_timeout_s: float = 8.0
    ortho_wms_url: str = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution"
    # NMT GUGiK (A6): POST GetHByPointList, paczki po 1000 punktów; łączny limit całej siatki
    nmt_url: str = "https://services.gugik.gov.pl/nmt/"
    nmt_timeout_s: float = 12.0
    nmt_total_timeout_s: float = 25.0     # A9: teren liczony w tle / GET /api/terrain – nie w budżecie analizy
    terrain_background: bool = True       # A9: analiza bez terenu w cache → {status: pending} + liczenie w tle
    nmt_retry_delay_s: float = 0.3
    # A8: najwyżej 2 paczki naraz (GUGiK spokojnie); 1 = po kolei z przerwą nmt_chunk_pause_s (warm_demo: 1 / 1,0 s).
    # „Brak 51% wysokości” nie był winą równoległości, tylko dopasowania współrzędnych (nmt.match_heights).
    nmt_parallel: int = 2
    nmt_chunk_pause_s: float = 0.5
    # zapasowe wyniki terenu z app/data/terrain (prawdziwe NMT z 21.11, osoba C) – gdy NMT nie odpowiada (D57)
    terrain_saved_results: bool = True

    # Sentinel-2 L2A (A11, D86): Earth Search STAC + COG (AWS) – to nie GUGiK
    sentinel_stac_url: str = "https://earth-search.aws.element84.com/v1/search"
    sentinel_budget_s: float = 15.0      # tryb na żywo: ok. 15 s …
    sentinel_budget_mb: float = 10.0     # … i ok. 10 MB na działkę
    sentinel_timeout_s: float = 6.0      # pojedyncze zapytanie (STAC / kafel COG); przerwany odczyt – 1 ponowienie
    sentinel_breaker_s: float = 120.0
    sentinel_cache_ttl_today_s: float = 43_200  # wynik dla „dziś” – 12 h (nowe przeloty co 2–5 dni)
    sentinel_background: bool = True     # analiza bez wyniku w cache uruchamia liczenie w tle
    sentinel_enabled: bool = True        # False = bez zapytań do Earth Search (testy) – tylko cache

    # opad ze stacji IMGW (A7, D82): magazyn app/data/imgw/opady.npz; wyłączony = opad z NASA POWER jak przed A7
    imgw_enabled: bool = True
    imgw_store: str = ""                 # ścieżka magazynu (puste = app/data/imgw/opady.npz)
    imgw_max_km: float = 30.0            # stacje w promieniu 30 km …
    imgw_fallback_km: float = 50.0       # … a gdy brak – do 50 km (pewność o poziom niżej)
    imgw_max_stations: int = 3

    # wyszukiwanie miejsc po nazwie (A5c, D73): PRNG GUGiK (WFS) → rezerwa Nominatim OSM → słownik demo
    prng_url: str = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRNG/WFS/GeographicalNames"
    prng_timeout_s: float = 8.0
    prng_min_interval_s: float = 1.2     # odstęp między zapytaniami do PRNG (po serii szybkich zapytań serwer odrzuca połączenia)
    prng_retry_delay_s: float = 3.0
    prng_breaker_s: float = 60.0
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    nominatim_timeout_s: float = 6.0
    nominatim_min_interval_s: float = 1.1  # polityka OSM: najwyżej 1 zapytanie na sekundę
    nominatim_breaker_s: float = 60.0
    # A9: adresy PRG – UUG GUGiK (klucz `uug` w OFFLINE_SOURCES), rezerwa Nominatim
    uug_url: str = "https://services.gugik.gov.pl/uug/"
    uug_timeout_s: float = 6.0
    uug_breaker_s: float = 120.0
    search_addresses: bool = True
    # A9: woda w okolicy – Overpass (OSM) i stany wód IMGW, liczone w tle
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    # rezerwowe instancje (po kolei przy 5xx / 429 / przekroczonym czasie) – publiczny Overpass bywa przeciążony
    # P1 (pomiar 22.11.2026): overpass.openstreetmap.fr odpowiada w ok. 1 s, pozostałe 15–60 s albo wcale
    overpass_fallback_urls: str = ("https://overpass.openstreetmap.fr/api/interpreter,"
                                   "https://overpass.private.coffee/api/interpreter,"
                                   "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
    overpass_timeout_s: float = 15.0      # P1: limit całej wody w okolicy (routery czekają +10 s); było 55 s
    overpass_query_timeout_s: float = 10.0   # P1: [timeout:10] w zapytaniu Overpass
    overpass_server_timeout_s: float = 8.0   # P1: najwyżej 8 s na serwer (wszystkie pytane równolegle)
    overpass_total_timeout_s: float = 15.0   # P1: najwyżej 15 s łącznie
    overpass_breaker_s: float = 300.0
    imgw_hydro_url: str = "https://danepubliczne.imgw.pl/api/data/hydro"
    hydro_background: bool = True        # A9: adresy w wyszukiwarce (testy A5c – bez, jawnie włączane w test_a9)
    search_timeout_s: float = 14.0        # łączny limit jednego wyszukiwania
    # A19: „gmina + numer” – najwyżej tyle obrębów gminy sprawdzamy w ULDK na jedno zapytanie (sekwencyjnie) i tyle
    # sekund (od startu wyszukiwania) na całe sprawdzanie – reszta budżetu zostaje na odpowiedź
    search_gmina_max_obreby: int = 10
    search_gmina_budget_s: float = 10.0

    # przykłady demo: rozgrzewka cache przy starcie (w tle) i co tyle godzin
    demo_warmup: bool = True
    demo_warmup_interval_h: float = 6.0
    demo_warmup_delay_s: float = 120.0  # A22: rozgrzewka startuje tyle sekund po uruchomieniu (DEMO_WARMUP_DELAY_S)
    # adres aplikacji w kodzie QR raportu PDF
    public_url: str = ""  # PUBLIC_URL – publiczny adres aplikacji; puste = bez kodu QR w raporcie PDF (A5b-2c)


settings = Settings()
