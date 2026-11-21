from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfiguracja aplikacji (zmienne środowiskowe lub plik .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    http_timeout_s: float = 20.0
    user_agent: str = "zatrzymaj-wode/0.1 (HackNation 2026)"
    cors_origins: list[str] = ["http://localhost:5173"]

    uldk_url: str = "https://uldk.gugik.gov.pl/"
    iung_wms_url: str = "https://sgeo.iung.pl/geoserver/Susza/wms"
    iung_soil_layer: str = "Susza:katgl_landuse2024"
    nasa_power_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"

    # ile punktów w obrysie działki sprawdzamy w mapie gleb IUNG
    soil_sample_points: int = 9
    # ile lat wstecz pobieramy dane pogodowe
    history_years: int = 10


settings = Settings()
