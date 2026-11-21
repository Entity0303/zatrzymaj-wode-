import httpx

from app.config import settings

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
    """Błąd zewnętrznego źródła danych (niedostępne, zła odpowiedź, brak wyników)."""

    def __init__(self, source: str, message: str):
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message
