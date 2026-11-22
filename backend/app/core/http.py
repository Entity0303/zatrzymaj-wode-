import asyncio
import time

import httpx

from app.core.config import settings

_client: httpx.AsyncClient | None = None
DEFAULT_MAX_BYTES = 30_000_000  # największa zwykła odpowiedź: NASA POWER 10 lat / IUNG WCS – kilka MB


def get_client() -> httpx.AsyncClient:
    """Wspólny klient HTTP (połączenia są ponownie wykorzystywane). NIGDY nie podąża za przekierowaniami (A6, D56):
    GUGiK przy limicie odsyła na integracja01.gugik.gov.pl/resp/uldk.php, który serwuje plik ~126 MB."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=settings.http_timeout_s,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=False,
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


class RedirectBlocked(SourceError):
    """Źródło odpowiedziało przekierowaniem (3xx) – traktujemy jak blokadę / ograniczenie ruchu; treści nie czytamy."""

    def __init__(self, source: str, location: str | None = None):
        super().__init__(source, "usługa chwilowo ogranicza ruch (przekierowanie) – spróbuj za chwilę")
        self.location = location


# D89: klucz OFFLINE_SOURCES → fragment nazwy źródła (SourceError.source / nazwa cache)
OFFLINE_KEYS = {"uldk": "ULDK", "nmt": "NMT", "kieg": "KIEG", "uug": "UUG", "bdot": "BDOT", "prng": "PRNG",
                "soil_map": "Mapa glebowo-rolnicza", "ortho": "Ortofotomapa"}
SOURCE_OFF_MESSAGE = "usługa wyłączona na czas demo (OFFLINE_SOURCES) – tylko dane z pamięci podręcznej"


def offline_keys() -> set[str]:
    return {k.strip().lower() for k in (settings.offline_sources or "").split(",") if k.strip()}


def source_offline(source: str | None) -> bool:
    """Czy źródło jest wyłączone pojedynczo (OFFLINE_SOURCES)? Dopasowanie po fragmencie nazwy źródła."""
    if not source:
        return False
    low = source.lower()
    return any(OFFLINE_KEYS.get(k, k).lower() in low for k in offline_keys())


_gugik_state: dict[int, dict] = {}  # stan limitu GUGiK na pętlę zdarzeń (semafor nie przechodzi między pętlami)


def is_gugik(source: str | None) -> bool:
    return bool(source) and "gugik" in source.lower()


async def _gugik_wait(st: dict) -> None:
    """Odstęp ≥ `gugik_min_interval_s` między startami zapytań do GUGiK (A8, D89)."""
    async with st["lock"]:
        wait = st["last"] + settings.gugik_min_interval_s - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        st["last"] = time.monotonic()


async def request(method: str, url: str, *, source: str, **kw) -> httpx.Response:
    """Wspólne wejście: dla usług GUGiK – limit zapytań naraz (`gugik_parallel`) i odstęp między nimi (D89);
    reszta bez zmian (`_request`)."""
    if not is_gugik(source) or settings.demo_offline or source_offline(source):
        return await _request(method, url, source=source, **kw)
    loop = asyncio.get_running_loop()
    st = _gugik_state.get(id(loop))
    if st is None or st["loop"] is not loop:
        st = _gugik_state[id(loop)] = {"loop": loop, "sem": asyncio.Semaphore(max(1, settings.gugik_parallel)),
                                       "lock": asyncio.Lock(), "last": 0.0}
    async with st["sem"]:
        await _gugik_wait(st)
        return await _request(method, url, source=source, **kw)


async def _request(
    method: str,
    url: str,
    *,
    source: str,
    timeout_s: float,
    params: dict | list[tuple[str, str]] | None = None,
    data: dict | None = None,
    headers: dict | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    content: bytes | None = None,
) -> httpx.Response:
    """Jedno zapytanie (bez ponowień) z odczytem strumieniowym:
    - przekierowanie 3xx → `RedirectBlocked` BEZ czytania treści (połączenie zamykane od razu),
    - treść większa niż `max_bytes` (zadeklarowana albo w trakcie odczytu) → SourceError i przerwanie,
    - łączny czas odczytu > 2 × `timeout_s` → SourceError (limit httpx dotyczy pojedynczej operacji).
    Zwraca odpowiedź z wczytaną treścią (status 2xx/4xx/5xx – decyzja należy do wołającego).
    Wyjątki httpx (timeout, brak połączenia) przechodzą dalej – obsługują je wołający."""
    if settings.demo_offline:  # D55: w trybie demo offline nie wysyłamy żadnych zapytań zewnętrznych
        raise SourceError(source, "tryb demo offline – bez połączenia z usługą")
    if source_offline(source):  # D89: pojedyncze źródło wyłączone (OFFLINE_SOURCES) – tylko cache
        raise SourceError(source, SOURCE_OFF_MESSAGE)
    client = get_client()
    req = client.build_request(method, url, params=params, data=data, headers=headers, content=content,
                               timeout=httpx.Timeout(timeout_s))
    t0 = time.monotonic()
    try:
        resp = await client.send(req, stream=True, follow_redirects=False)
    except httpx.DecodingError as exc:
        raise SourceError(source, "usługa zwróciła uszkodzoną odpowiedź (kompresja)") from exc
    try:
        if 300 <= resp.status_code < 400:
            raise RedirectBlocked(source, resp.headers.get("location"))
        declared = resp.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise SourceError(source, f"odpowiedź za duża ({int(declared) // 1_000_000} MB) – przerwano")
        chunks, size = [], 0
        try:
            async for part in resp.aiter_bytes():
                size += len(part)
                if size > max_bytes:
                    raise SourceError(source, f"odpowiedź za duża (> {max_bytes // 1_000_000} MB) – przerwano")
                if time.monotonic() - t0 > 2 * timeout_s:
                    raise SourceError(source, f"odczyt odpowiedzi trwa ponad {2 * timeout_s:.0f} s – przerwano")
                chunks.append(part)
        except httpx.DecodingError as exc:  # uszkodzona kompresja (np. strona blokady GUGiK) – awaria źródła, nie 500
            raise SourceError(source, "usługa zwróciła uszkodzoną odpowiedź (kompresja)") from exc
    finally:
        await resp.aclose()
    # treść jest już rozpakowana (aiter_bytes) – bez nagłówków kodowania, inaczej httpx rozpakowałby ją drugi raz
    headers = [(k, v) for k, v in resp.headers.multi_items()
               if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")]
    return httpx.Response(resp.status_code, headers=headers, content=b"".join(chunks), request=req)


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


async def get_with_retry(
    url: str,
    params: dict | list[tuple[str, str]],
    *,
    source: str,
    timeout_s: float,
    retries: int = 1,
    max_bytes: int = DEFAULT_MAX_BYTES,
):
    """GET z timeoutem i ponowną próbą przy błędzie sieci / timeoucie / 5xx (przez `request` – bez przekierowań).

    3xx (RedirectBlocked), 429 (limit zapytań) i pozostałe 4xx = niedostępność źródła bez ponawiania.
    Każda porażka kończy się SourceError(source, komunikat po polsku).
    """
    last = "brak odpowiedzi"
    for attempt in range(retries + 1):
        try:
            resp = await request("GET", url, source=source, timeout_s=timeout_s, params=params, max_bytes=max_bytes)
        except httpx.TimeoutException:
            last = f"usługa nie odpowiada (przekroczono {timeout_s:.0f} s)"
            continue
        except httpx.TransportError as exc:
            last = f"brak połączenia z usługą ({exc.__class__.__name__})"
            continue
        if resp.status_code == 429:
            raise SourceError(source, "przekroczony limit zapytań (HTTP 429)")
        if resp.status_code >= 500:
            last = f"usługa zwróciła błąd HTTP {resp.status_code}"
            continue
        if resp.status_code >= 400:
            raise SourceError(source, f"usługa zwróciła błąd HTTP {resp.status_code}")
        return resp
    raise SourceError(source, last)
