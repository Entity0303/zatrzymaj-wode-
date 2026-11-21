import httpx

from app.core.config import settings

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Wspólny klient HTTP (połączenia są ponownie wykorzystywane)."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=settings.http_timeout_s,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class SourceError(Exception):
    """Błąd zewnętrznego źródła danych (niedostępne lub zła odpowiedź) -> HTTP 502."""

    def __init__(self, source: str, message: str):
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message


class NotFoundError(SourceError):
    """Źródło odpowiedziało poprawnie, ale nie ma szukanego obiektu -> HTTP 404."""


def http_error(exc: SourceError):
    """SourceError -> HTTPException: brak obiektu = 404, awaria źródła = 502 z nazwą źródła."""
    from fastapi import HTTPException

    status = 404 if isinstance(exc, NotFoundError) else 502
    return HTTPException(status_code=status, detail={"source": exc.source, "message": exc.message})


def not_implemented(what: str):
    """Szkielet endpointu – HTTP 501 „w budowie”."""
    from fastapi import HTTPException

    return HTTPException(status_code=501, detail={"message": f"{what} – w budowie"})


POLAND_BBOX = (14.0, 49.0, 24.2, 55.0)  # lon_min, lat_min, lon_max, lat_max


def in_poland(lon: float, lat: float) -> bool:
    return POLAND_BBOX[0] <= lon <= POLAND_BBOX[2] and POLAND_BBOX[1] <= lat <= POLAND_BBOX[3]
