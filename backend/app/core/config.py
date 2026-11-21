from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfiguracja aplikacji (zmienne środowiskowe lub plik .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    http_timeout_s: float = 20.0
    user_agent: str = "zatrzymaj-wode/0.1 (HackNation 2026)"
    cors_origins: list[str] = ["http://localhost:5173"]

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

    # cache (D44): dane bieżące 6 h, historyczne i stałe (działki, mapy gleb) 7 dni
    cache_ttl_current_s: float = 6 * 3600
    cache_ttl_history_s: float = 7 * 24 * 3600

    soilgrids_url: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    soilgrids_timeout_s: float = 12.0
    soil_map_url: str = "https://mapy.geoportal.gov.pl/wss/service/pub/guest/MapaGlebowoRolnicza/MapServer/WMSServer"
    soil_map_timeout_s: float = 8.0
    ortho_wms_url: str = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution"

    # przykłady demo: rozgrzewka cache przy starcie (w tle) i co tyle godzin
    demo_warmup: bool = True
    demo_warmup_interval_h: float = 6.0
    # adres aplikacji w kodzie QR raportu PDF
    public_url: str = "http://localhost:5173"


settings = Settings()
