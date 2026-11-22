"""Raport PDF „Paszport wodny działki” (SPEC 10.2) – WeasyPrint, A4 pionowo. Bez uprawy (A5b-1) – krótszy
raport „Stan wodny działki”: gleba, zapas wody pod pokryciem referencyjnym FAO-56, bilans, retencja.

Treść = wynik normalnej analizy (run_analysis) + mapa działki (ortofotomapa Geoportalu, WMS GetMap przycięta do
obrysu z marginesem) + wykresy SVG (charts.py) + kod QR do analizy online (tylko gdy ustawiony PUBLIC_URL). Raport nie liczy
niczego sam – tylko przedstawia wynik analizy.
"""

import asyncio
import base64
import os
import datetime as dt
import re
from pathlib import Path
from urllib.parse import urlencode

import segno
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from shapely.geometry import shape

from app.analysis.crops import CROPS
from app.analysis.scoring import status_cfg
from app.core.config import settings
from app.core.geo import to_2180
from app.core.cache import TTLCache, cached_fetch
from app.core.http import SourceError, get_with_retry
from app.report import charts
from app.schemas.analysis import AnalysisResponse

HERE = Path(__file__).parent
ORTHO_TIMEOUT_S = 6.0
MAP_PX = 560

STATUS = {  # SPEC 2.2
    # F21: nazwy stopni jak w backendzie (scoring / rules/status.yaml): W normie / Uwaga / Mało wody / Bardzo mało wody
    "ok": ("W normie", "#5BB37F", "#E6F4EA"), "warn": ("Uwaga", "#E8B931", "#FDF4D8"),
    "risk": ("Mało wody", "#E07B39", "#FCEBDD"), "danger": ("Bardzo mało wody", "#C8453B", "#FBE7E5"),
    "no_data": ("Brak danych", "#B8BDB9", "#F1F2F1"),
}
CATEGORY = {"retencja": ("Zatrzymanie wody", "#2F80C9"), "agrotechnika": ("Zmiany w uprawie", "#8B6B4A"),
            "nawadnianie": ("Nawadnianie", "#2F6B47")}
PERMIT_ICON = {"none": "✓", "maybe": "!", "required": "§"}
SOURCE_ICON = {"ok": "✓", "czesciowo": "⚠", "brak": "×"}
CONFIDENCE = {"wysoka": "wysoka", "srednia": "średnia", "ograniczona": "ograniczona"}
RAIN = {"ucieka": "szybko wsiąka i ucieka w głąb", "zatrzymuje": "dobrze ją zatrzymuje",
        "splywa": "ryzyko spływu i zastoisk"}


# ── filtry szablonu ─────────────────────────────────────────────────────────────────────────


def num(v, dec: int = 0, unit: str = "") -> str:
    if v is None:
        return "brak danych"
    txt = f"{v:.{dec}f}".replace(".", ",").replace("-", "−")
    if not unit:
        return txt
    return f"{txt}{unit}" if unit == "%" else f"{txt} {unit}"


def pct(v) -> str:
    return "brak danych" if v is None else f"{round(100 * v)}%"


def date_pl(d) -> str:
    if d is None:
        return "brak"
    if isinstance(d, dt.datetime):
        return d.astimezone().strftime("%d.%m.%Y %H:%M")
    return d.strftime("%d.%m.%Y")


_env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
def first_sentence(text: str | None) -> str:
    """Pierwsze zdanie (karta działania: „dlaczego” w jednej linijce)."""
    if not text:
        return ""
    m = re.search(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])", text)
    return text[: m.start()] if m else text


def sentences(text: str | None, n: int = 2) -> str:
    """Pierwsze `n` zdań (karta działania w raporcie skróconym: 1–2 zdania)."""
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])", text.strip())
    return " ".join(parts[:n])


def clip(text: str | None, n: int = 170) -> str:
    """Skrót do `n` znaków na granicy słowa (raport skrócony – zawsze 2 strony)."""
    if not text or len(text) <= n:
        return text or ""
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:–-")
    return cut + "…"


def whole(text: str | None, n: int = 150) -> str:
    """F24: skrót BEZ wielokropka – tyle pełnych zdań, ile mieści się w `n` znakach; gdy już pierwsze zdanie jest za
    długie, ucinamy je na granicy członu (średnik, myślnik, przecinek) i kończymy kropką; ostatecznie całe zdanie."""
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])", text.strip())
    out = parts[0]
    for p in parts[1:]:
        if len(out) + 1 + len(p) > n:
            break
        out += " " + p
    if len(out) <= n:
        return out
    for sep in ("; ", " – ", ", "):
        cut = out[:n].rfind(sep)
        if cut >= n * 0.5:
            return out[:cut].rstrip(" ,;–") + "."
    return out


def tidy(text: str | None) -> str:
    """F24: bez powtórzeń w opisie działania – „95% pełnego (zapas wody w glebie pełny)” → „95% pełnego”."""
    return re.sub(r"(% pełnego) \((?:zapas wody w glebie (?:prawie )?pełny)\)", r"\1", text or "")


_env.filters.update(whole=whole, tidy=tidy, num=num, pct=pct, date_pl=date_pl, first_sentence=first_sentence, sentences=sentences, clip=clip)
REPORT_LABEL = {"short": "Raport skrócony", "full": "Raport szczegółowy"}
REPORT_SLUG = {"short": "skrocony", "full": "szczegolowy"}
SHORT_RECS = 4
SHORT_LIMITATIONS = 5


# ── mapa i kod QR ───────────────────────────────────────────────────────────────────────────


def map_frame(geometry_4326: dict, px: int = MAP_PX) -> tuple[tuple[float, float, float, float], str]:
    """Kwadratowy wycinek (EPSG:2180) wokół działki z marginesem + obrys w pikselach (SVG)."""
    g = to_2180(shape(geometry_4326))
    minx, miny, maxx, maxy = g.bounds
    side = max(maxx - minx, maxy - miny) * 1.5 + 60  # margines, min. ok. 60 m
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    bbox = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    rings = [[((x - bbox[0]) / side * px, (bbox[3] - y) / side * px) for x, y in p.exterior.coords] for p in polys]
    return bbox, charts.outline_svg(rings, px, px)


ORTHO_SOURCE = "Ortofotomapa GUGiK"
_ortho_cache: TTLCache[str] = TTLCache(ttl_s=None, max_items=128, name=ORTHO_SOURCE)  # bez wygasania (D53)


async def ortho_image(bbox: tuple[float, float, float, float], px: int = MAP_PX) -> str | None:
    """Ortofotomapa Geoportalu jako data URI – z cache (także w trybie demo offline), None = niedostępna."""
    key = (tuple(round(v, 1) for v in bbox), px)
    try:
        return await cached_fetch(_ortho_cache, key, ORTHO_SOURCE, lambda: _ortho_download(bbox, px))
    except SourceError:
        return None


async def _ortho_download(bbox: tuple[float, float, float, float], px: int) -> str:
    """WMS GetMap, EPSG:2180 – BBOX w kolejności północ, wschód."""
    minx, miny, maxx, maxy = bbox
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": "Raster", "STYLES": "",
        "CRS": "EPSG:2180", "BBOX": f"{miny},{minx},{maxy},{maxx}", "WIDTH": str(px), "HEIGHT": str(px),
        "FORMAT": "image/jpeg",
    }
    try:
        resp = await asyncio.wait_for(
            get_with_retry(settings.ortho_wms_url, params, source="Ortofotomapa GUGiK", timeout_s=ORTHO_TIMEOUT_S,
                           retries=0), ORTHO_TIMEOUT_S + 1)
    except asyncio.TimeoutError as exc:
        raise SourceError(ORTHO_SOURCE, "brak odpowiedzi") from exc
    ctype = resp.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        raise SourceError(ORTHO_SOURCE, "odpowiedź nie jest obrazem")
    return f"data:{ctype.split(';')[0]};base64,{base64.b64encode(resp.content).decode()}"


def zones_overlay(a: AnalysisResponse, bbox: tuple[float, float, float, float], px: int = MAP_PX) -> str:
    """Mapka stref terenu (A6): strefy z /api/layers/teren w tym samym wycinku co ortofotomapa (EPSG:2180 → piksele)."""
    if a.terrain is None:
        return ""
    from app.analysis import terrain as terrain_mod
    from app.analysis import terrain_interpret

    try:
        res = terrain_mod._memo_lookup(a.parcel.id)
    except Exception:  # noqa: BLE001
        res = None
    if res is None:
        return ""
    feats = terrain_interpret.layer_teren(res.geojson, res.facts, shape(a.parcel.geometria))["features"]
    side = bbox[2] - bbox[0]
    shapes = []
    for f in feats:
        g = to_2180(shape(f["geometry"]))
        polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g] if g.geom_type == "Polygon" else []
        rings = [[((x - bbox[0]) / side * px, (bbox[3] - y) / side * px) for x, y in p.exterior.coords] for p in polys]
        shapes.append((f["properties"]["color"], rings))
    return charts.zones_svg(shapes, px, px)


LEVEL = {"ok": ("✓", "#5BB37F"), "warn": ("!", "#E8B931"), "bad": ("×", "#C8453B"), "info": ("i", "#2F80C9")}
CAT_ICON = {"polecane": ("✓", "#5BB37F"), "mozliwe": ("~", "#E8B931"), "odradzane": ("×", "#C8453B")}
KIND_LABEL = {"gleba": "Gleba", "opady": "Opady", "teren": "Teren", "rosliny": "Rośliny (z satelity)", "uprawy": "Co siać",
              "woda": "Woda",
              "uprawa_wybrana": "Wybrana uprawa"}


def parcel_name(a: AnalysisResponse) -> tuple[str, str]:
    p = a.parcel
    if a.approximate_area:
        lon, lat = a.approximate_area.center
        return (f"Obszar przybliżony ({lat:.4f} N, {lon:.4f} E)",
                f"ok. {a.approximate_area.area_ha:g} ha · woj. {p.wojewodztwo} (przybliżone)")
    if p.source == "drawn":
        where = ", ".join(x for x in (f"gm. {p.gmina}" if p.gmina not in ("", "nieznana") else "",
                                       p.powiat if p.powiat not in ("", "nieznany") else "") if x)
        return (p.name or "Pole narysowane przez rolnika",
                f"{num(p.powierzchnia_ha, 2, 'ha')} (z kształtu) · {where + ' · ' if where else ''}woj. {p.wojewodztwo} · "
                "nie jest działką ewidencyjną")
    return (f"Działka {p.numer}, obręb {p.obreb}",
            f"gm. {p.gmina}, {p.powiat}, woj. {p.wojewodztwo} · {p.id} · {num(p.powierzchnia_ha, 2, 'ha')}")


def water_actions(a: AnalysisResponse) -> list:
    """3 działania wodne na stronę 1 – retencja przed agrotechniką, bez niepewnych (z ostrzeżeniem)."""
    recs = [r for r in a.recommendations if r.category in ("retencja", "agrotechnika")]
    recs.sort(key=lambda r: (r.category != "retencja", bool(r.warning), not r.in_panel))
    return recs[:3]


def history_labels(a: AnalysisResponse) -> str:
    from app.analysis.crops import ALL_CROPS

    names = ["rok temu", "2 lata temu", "3 lata temu"]
    parts = [f"{names[k]}: {ALL_CROPS[h].label.lower() if h in ALL_CROPS else 'nie wiem'}" for k, h in enumerate(a.crop_history)]
    return "; ".join(parts)


def analysis_url(a: AnalysisResponse) -> str:
    if a.parcel.source == "drawn":  # obrysu nie da się zapisać w adresie – link do aplikacji
        return app_url() + "/"
    if a.approximate_area:
        lon, lat = a.approximate_area.center
        # frontend (lib/deepLink.ts) nie obsługuje lon/lat – link z samą datą
        return f"{app_url()}/?{urlencode({'data': a.analysis_date.isoformat()})}"
    q = {"dzialka": a.parcel.id}
    if a.crop:
        q["uprawa"] = a.crop
    q["data"] = a.analysis_date.isoformat()
    if a.previous_crop:
        q["przedplon"] = a.previous_crop
    return f"{app_url()}/?{urlencode(q)}"


def qr_svg(url: str) -> str:
    svg = segno.make(url, error="m").svg_inline(scale=2.2, border=1, dark="#1E2A23")
    return re.sub(r"<\?xml[^>]*\?>", "", svg)


# ── składanie ───────────────────────────────────────────────────────────────────────────────


def filename(a: AnalysisResponse, report_type: str = "short") -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "-", a.parcel.id).strip("-")
    kind = "paszport-wodny" if a.crop else "stan-wodny-dzialki"
    return f"{kind}-{safe}-{a.analysis_date.isoformat()}-{REPORT_SLUG.get(report_type, 'skrocony')}.pdf"


def top_limitations(a: AnalysisResponse, n: int = SHORT_LIMITATIONS) -> list[str]:
    """5 najważniejszych ograniczeń: obszar przybliżony / pole narysowane, pogoda, braki danych, potem reszta
    (kolejność z `reliability.limitations` – tam najważniejsze są na początku)."""
    return list(a.reliability.limitations[:n])


def soil_short(a: AnalysisResponse) -> str:
    if a.terrain and a.terrain.soil_group_label:
        return a.terrain.soil_group_label.split(":")[0]
    v = a.verdict
    if v:
        g = next((s for s in v.statements if s.kind == "gleba"), None)
        if g and g.numbers.get("grupa"):
            return {"lekka": "gleba lekka", "srednia": "gleba średnia", "ciezka": "gleba ciężka",
                    "organiczna": "gleba organiczna"}.get(str(g.numbers["grupa"]), a.soil.dominant_label or "brak danych")
    return a.soil.dominant_label or "brak danych"


def price_weather_block(a: AnalysisResponse) -> dict | None:
    """F32 (raport pełny): „Ceny i pogoda na tle lat” dla województwa działki i najwyższej w rankingu uprawy z ceną GUS –
    te same dane co GET /api/price-weather (porównanie regionalne, nie dla działki). Brak danych → None (bez karty)."""
    from app.analysis import price_weather as PW

    try:
        region = PW.region_key(a.parcel.wojewodztwo) or PW.PL
        ranked = [i.crop_id for i in field_items(a)] + ([a.crop] if a.crop else [])
        crop = next((c for c in ranked if PW.product_for(c)), "pszenica")
        data = PW.cached(region, crop, a.analysis_date.year)
    except Exception:  # noqa: BLE001 – karta dodatkowa; jej brak nie może wywrócić raportu
        return None
    if data.get("unavailable"):
        return None
    chart = charts.price_weather_chart(data["years"], data["dry_years"])
    return {**data, "chart": Markup(chart)} if chart else None


def top_items(a: AnalysisResponse) -> list:
    s = a.suggestions
    if not s:
        return []
    field = [i for g in s.groups if g.key == "polowe" for i in g.items]
    ids = s.top_ids or [i.crop_id for i in field if i.category != "odradzane"][:5]
    return [i for i in field if i.crop_id in ids]


def satellite_overlay(a: AnalysisResponse, bbox: tuple[float, float, float, float]) -> tuple[str | None, str]:
    """PNG NDVI z cache satelity + pozycja na mapce raportu (CSS w % wycinka EPSG:2180)."""
    if a.satellite is None or a.satellite.status != "ok":
        return None, ""
    from app.analysis import satellite as satellite_mod

    lay = satellite_mod.cached_layers(shape(a.parcel.geometria), a.analysis_date)
    if not lay or not lay.get("kondycja"):
        return None, ""
    lo0, la0, lo1, la1 = lay["bbox"]
    g = to_2180(shape({"type": "Polygon", "coordinates": [[[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1], [lo0, la0]]]}))
    minx, miny, maxx, maxy = g.bounds
    side = bbox[2] - bbox[0]
    style = (f"left:{(minx - bbox[0]) / side * 100:.2f}%;top:{(bbox[3] - maxy) / side * 100:.2f}%;"
             f"width:{(maxx - minx) / side * 100:.2f}%;height:{(maxy - miny) / side * 100:.2f}%")
    return "data:image/png;base64," + lay["kondycja"], style


# ── F19: raport w stylu paszportu – dane gotowe do szablonu (bez liczenia: tylko wybór i formatowanie) ──────────

NOW_LABEL = {"ok": "woda w normie", "warn": "mało wody", "risk": "brakuje wody", "danger": "bardzo mało wody",
             "no_data": "brak danych"}
LONG_LABEL = {"ok": "niskie ryzyko suszy", "warn": "średnie ryzyko suszy", "bad": "wysokie ryzyko suszy"}
POINT_KINDS = ["gleba", "opady", "teren", "rosliny", "uprawa_wybrana"]
CAT_ORDER = {"retencja": 0, "agrotechnika": 1, "nawadnianie": 2}
CAT_TEXT = {"polecane": ("polecana", "#5BB37F"), "mozliwe": ("możliwa", "#E8B931"), "odradzane": ("odradzana", "#C8453B")}
PERMIT_TEXT = {"none": "bez formalności", "maybe": "sprawdź formalności", "required": "wymaga zgłoszenia"}
# zawsze prawdziwe dla metody – w ramce „Skąd dane i pewność” (wymóg KOWR)
STANDARD_LIMITS = [
    "Wody gruntowe nie są uwzględnione – liczymy wodę z opadów i parowania w strefie korzeni.",
    "Teren opisujemy z modelu GUGiK; nie zmienia on obliczonego bilansu wody.",
    "Typowy plon to wynik z pogody 10 lat, nie prognoza na ten rok.",
]
# to samo krótko – ramka na stronie 2 raportu skróconego
STANDARD_LIMITS_SHORT = "bez wód gruntowych; teren nie zmienia obliczonego bilansu; typowy plon z 10 lat, nie prognoza na ten rok"


def balance_words(mm: float | None) -> str:
    """Bilans wody słowami: ujemny = „zabrakło 120 mm”, dodatni = „zostało 35 mm”."""
    if mm is None:
        return "brak danych"
    v = round(mm)
    return f"zabrakło {num(abs(v))} mm" if v < 0 else f"zostało {num(v)} mm" if v > 0 else "0 mm"


def tonnes(v: float | None) -> str:
    """Tony z pola po ludzku: „ok. 430 t” (≥ 100 – do 10 t), „ok. 43 t”, „ok. 4,3 t”."""
    if v is None:
        return "brak danych"
    if v >= 100:
        return f"ok. {num(round(v, -1))} t"
    if v >= 10:
        return f"ok. {num(round(v))} t"
    return f"ok. {num(v, 1)} t"


def zl(v: float | None) -> str | None:
    """Kwota do 100 zł z twardą spacją tysięcy: „ok. 2 100 zł”; brak / ≤ 0 = None (nigdy „0 zł”)."""
    if v is None or v <= 0:
        return None
    r = int(round(v / 100) * 100)
    return "ok. " + f"{r:,}".replace(",", " ") + " zł"


def _span(r) -> tuple[float, float] | None:
    """F21: [min, max] z wariantów A21 (None, gdy brak / niepełne)."""
    if not r or len(r) < 2 or r[0] is None or r[1] is None:
        return None
    return (min(r[0], r[1]), max(r[0], r[1]))


def risk_text(i) -> str:
    """„3 na 10 lat” albo zakres „1–4 na 10 lat” (A21 drought_risk_range); min = max – jedna liczba."""
    rng = _span(getattr(i, "drought_risk_range", None) or getattr(i, "risk_years_range", None))
    n = f"{int(rng[0])}–{int(rng[1])}" if rng and rng[0] != rng[1] else str(i.drought_risk_years)
    return f"{n} na {i.years_simulated} lat"


def yield_text(v: float | None, rng=None) -> str:
    """F21: plon „3,4–3,9 t/ha” z widełek albo „3,6 t/ha”; brak = „brak danych”."""
    s = _span(rng)
    if s and num(s[0], 1) != num(s[1], 1):
        return f"{num(s[0], 1)}–{num(s[1], 1)} t/ha"
    return num(v, 1, "t/ha")


def zl_range(rev) -> str | None:
    """Przychód „4 600–5 200 zł” z revenue_range (A21) albo „ok. 4 900 zł”; brak ceny = None."""
    if not rev or zl(rev.typical_zl) is None:
        return None
    s = _span(getattr(rev, "revenue_range", None))
    if s and zl(s[0]) and zl(s[1]) and zl(s[0]) != zl(s[1]):
        return f"{zl(s[0])[4:-3]}–{zl(s[1])[4:]}"  # F24: zakres bez „ok.” („ok.” tylko przy jednej kwocie)
    return zl(rev.typical_zl)


def field_items(a: AnalysisResponse) -> list:
    s = a.suggestions
    return [i for g in s.groups if g.key == "polowe" for i in g.items] if s else []


def chosen_item(a: AnalysisResponse):
    """Pozycja rankingu dla wybranej uprawy (wybór rolnika → gatunek z grupy IUNG → najlepsza na działce)."""
    items = field_items(a)
    if not items:
        return None
    if a.suggestions and a.suggestions.choice:
        ids = [c.crop_id for c in a.suggestions.choice]
        hit = next((i for i in items if i.crop_id in ids), None)
        if hit:
            return hit
    if a.crop:
        group = sorted((i for i in items if i.group_id == a.crop), key=lambda i: i.rank)
        if group:
            return group[0]
    top = top_items(a)
    return top[0] if top else items[0]


FULL_RESERVE_PCT = 80.0  # F24: od tylu % zapasu nie porównujemy lat (o tej porze gleba zwykle jest pełna)
FULL_RESERVE_TEXT = "zapas prawie pełny – typowo dla tej pory roku"


def water_rank_text(rank, pct: float | None = None) -> str | None:
    """Porównanie zapasu z tą samą porą w 10 latach (`lower_years` = lata z MNIEJSZĄ ilością wody). F24: przy zapasie
    ≥ 80% zamiast rankingu lat „zapas prawie pełny – typowo dla tej pory roku”."""
    if pct is not None and pct >= FULL_RESERVE_PCT:
        return FULL_RESERVE_TEXT
    if not rank or not rank.of_years:
        return None
    n, of = rank.lower_years, rank.of_years
    if n == 0:
        return f"tak mało wody o tej porze nie było w żadnym z {of} lat"
    if n == of:
        return f"więcej wody niż w każdym z {of} lat o tej porze"
    if n >= of / 2:
        return f"więcej wody niż w {n} z {of} lat o tej porze"
    return f"mniej wody było tylko w {n} z {of} lat o tej porze"


def soil_chart_sentence(a: AnalysisResponse) -> str:
    """Zdanie-wniosek nad wykresem zapasu wody (z liczb analizy)."""
    f = a.field_state
    v = f.soil_water_pct.value if f else None
    if v is None:
        return "Brak danych o zapasie wody w glebie."
    txt = water_rank_text(f.soil_water.rank if f.soil_water else None, v)
    if txt == FULL_RESERVE_TEXT:  # bez powtórzenia słowa „zapas”
        txt = "typowo dla tej pory roku"
    return f"Teraz {num(v)}% pełnego zapasu{' – ' + txt if txt else ''}." if not a.historical else \
        f"W dniu analizy {num(v)}% pełnego zapasu{' – ' + txt if txt else ''}."


def precip_chart_sentence(a: AnalysisResponse) -> str:
    """Zdanie-wniosek nad wykresem opadów: miesiące poniżej 70% normy."""
    ms = [m for m in a.history.monthly_precip if m.current_mm is not None]
    if not ms:
        return "Brak danych o opadach w miesiącach."
    gaps = len(a.history.monthly_precip) - len(ms)  # F24: miesiące z niepełnymi danymi („?” na wykresie)
    loc = ["styczniu", "lutym", "marcu", "kwietniu", "maju", "czerwcu", "lipcu", "sierpniu", "wrześniu",
           "październiku", "listopadzie", "grudniu"]
    dry = [m for m in ms if m.mean_mm and m.current_mm < 0.7 * m.mean_mm]
    if not dry:
        return "W każdym miesiącu spadło co najmniej 70% tego, co zwykle."
    # łączny niedobór w suchych miesiącach względem normy z 10 lat (z liczb wykresu)
    norm = sum(m.mean_mm for m in dry)
    less = round((1 - sum(m.current_mm for m in dry) / norm) * 100 / 5) * 5
    mn = [loc[m.month - 1] for m in dry]
    if len(mn) > 3:
        return f"W {len(mn)} miesiącach spadło łącznie o ok. {less}% mniej niż zwykle."
    txt = mn[0] if len(mn) == 1 else ", ".join(mn[:-1]) + " i " + mn[-1]
    return (f"{'We' if txt.startswith('wrz') else 'W'} {txt} spadło o ok. {less}% mniej niż zwykle."
            + (" „?” = niepełne dane." if gaps else ""))


def app_url() -> str:
    """F20: adres aplikacji dla rolnika (frontend), nie backendu: FRONTEND_URL → PUBLIC_URL → https://wodoskop.vercel.app."""
    return (os.environ.get("FRONTEND_URL") or settings.public_url or "https://wodoskop.vercel.app").rstrip("/")


def tiles(a: AnalysisResponse) -> list[dict]:
    """4 kafle strony 1: zapas wody w glebie, bilans okresu, ryzyko suszy, przychód."""
    ind = a.indicators
    out = []
    w = ind.soil_water_pct.value
    rank = a.soil_water.rank if a.soil_water else None
    sub = water_rank_text(rank, w) or "zapas wody dostępnej dla roślin"
    out.append({"title": "Zapas wody w glebie", "value": "brak danych" if w is None else f"{num(w)}%",
                "unit": "pełnego" if w is not None else "", "sub": sub, "color": "#2F80C9", "bar": w})
    if a.period:
        mm, normal, label = a.period.balance_mm, a.period.normal_balance_mm, a.period.label
    else:
        cur = next((y for y in a.seasonal_balance_by_year if y.current), None)
        mm = cur.balance_mm if cur else ind.water_balance_season.value
        normal = a.seasonal_balance_mean_mm
        label = a.seasonal_balance_label or "od początku sezonu"
    out.append({"title": "Bilans wody (opad minus parowanie)", "value": balance_words(mm), "unit": "",
                "sub": (f"{label} · zwykle: {balance_words(normal)}" if normal is not None else label) +
                       (" · za cały sezon; jesienne opady uzupełniły glebę"
                        if mm is not None and mm < 0 and w is not None and w >= FULL_RESERVE_PCT else ""),
                "color": "#C8453B" if mm is not None and mm < 0 else "#2F80C9", "bar": None})
    it = chosen_item(a)
    if it:
        n = it.drought_risk_years
        out.append({"title": f"Ryzyko suszy – {it.label.lower()}", "value": risk_text(it), "unit": "",
                    "sub": "lata, w których susza zabiera ponad 20% plonu",
                    "color": "#C8453B" if n >= 5 else "#E07B39" if n >= 3 else "#5BB37F", "bar": None})
        typ = zl_range(it.revenue)
        weak = zl(it.revenue.weak_year_zl) if it.revenue else None
        out.append({"title": f"Przychód z pola – {it.label.lower()}", "value": typ or "brak ceny", "unit": "",
                    "sub": (f"typowy rok, bez kosztów{f' · słaby rok {weak}' if weak else ''}" if typ else
                            (it.revenue_note or "brak ceny skupu")),
                    "color": "#2F6B47", "bar": None})
    else:
        out.append({"title": "Ryzyko suszy", "value": "brak danych", "unit": "", "sub": "ranking upraw niedostępny",
                    "color": "#B8BDB9", "bar": None})
        out.append({"title": "Przychód z pola", "value": "brak danych", "unit": "", "sub": "ranking upraw niedostępny",
                    "color": "#B8BDB9", "bar": None})
    return out


def verdict_points(a: AnalysisResponse, n: int = 4) -> list:
    """3–4 punkty werdyktu w stałej kolejności: gleba, opady, teren, rośliny (potem wybrana uprawa)."""
    v = a.verdict
    if not v:
        return []
    by = {s.kind: s for s in v.statements}
    return [by[k] for k in POINT_KINDS if k in by][:n]


def avoid_groups(a: AnalysisResponse, max_groups: int = 2) -> list[tuple[str, list[str]]]:
    """„Unikaj:” pogrupowane po powodzie (maks. 2 linie): [(powód, [uprawy])]."""
    v = a.verdict
    if not v or not v.crops_bad:
        return []
    groups: dict[str, list[str]] = {}
    for c in v.crops_bad:
        groups.setdefault((c.reason or "odradzane na tej działce").rstrip("."), []).append(c.label.lower())
    return list(groups.items())[:max_groups]


def is_ditch(r) -> bool:
    txt = f"{r.title} {r.description}".lower()
    return "rów" in txt or "rowu" in txt or "zastawk" in txt


def actions(a: AnalysisResponse, n: int | None = 3) -> list:
    """Działania: retencja → agrotechnika → nawadnianie, w grupie wg priorytetu, bez powtórzeń (tytuł)."""
    recs = sorted(a.recommendations, key=lambda r: (CAT_ORDER.get(r.category, 9), bool(r.warning), -(r.priority or 0)))
    seen, out = set(), []
    for r in recs:
        key = r.title.strip().lower()
        if key in seen or r.id in seen:
            continue
        seen.update({key, r.id})
        out.append(r)
    return out if n is None else out[:n]


def source_date(s, analysis_date: dt.date) -> str:
    """„dane z dd.mm.rrrr” / „pobrano dd.mm.rrrr” (A20: data pobrania, gdy później niż data analizy)."""
    parts = []
    if s.data_date and s.data_date <= analysis_date:
        parts.append(f"dane z {date_pl(s.data_date)}")
    fetched = s.fetched_at or (s.data_date if s.data_date and s.data_date > analysis_date else None)
    if fetched:
        parts.append(f"pobrano {date_pl(fetched)}")
    return ", ".join(parts)


def sources_line(a: AnalysisResponse, limit: int | None = None) -> str:
    """Źródła w 1–2 liniach: „IMGW-PIB (dane z 29.06.2018); ULDK GUGiK (pobrano 21.11.2026); …”."""
    items = []
    for s in a.reliability.sources:
        if s.status == "brak":
            continue
        d = source_date(s, a.analysis_date)
        items.append(f"{s.name} ({d})" if d else s.name)
    if limit and len(items) > limit:
        rest = len(items) - limit
        items = items[:limit] + [f"i {rest} {'inne' if rest < 5 else 'innych'} (w raporcie pełnym)"]
    return "; ".join(items)


def period_text(a: AnalysisResponse) -> str:
    if a.period:
        txt = a.period.label
    else:
        txt = f"od {date_pl(a.history.season_start)} (sezon uprawy)"
    cs = a.crop_season
    if cs and cs.sowing_date:  # F21: data siewu rolnika (A21) i uwaga, gdy poza typowym zakresem
        txt += f" · siew {date_pl(cs.sowing_date)}"
    if cs and cs.sowing_note:
        txt += f" ({cs.sowing_note.rstrip('.')})"
    return txt


def area_text(a: AnalysisResponse, short: bool = False) -> str:
    """Powierzchnia działki + powierzchnia uprawy z notą, gdy są dwie różne (skrócony – nota do pierwszego zdania)."""
    ha = num(a.parcel.powierzchnia_ha, 2, "ha")
    s = a.suggestions
    if s and s.area and abs(s.area.value_ha - a.parcel.powierzchnia_ha) >= 0.01:
        note = s.area.note.rstrip('.')
        if short:
            note = note.split(':', 1)[0].split('. ')[0]
        return f"{ha} · uprawa {num(s.area.value_ha, 2, 'ha')} ({note.lower() if short else note})"
    return ha


# Teren nie zdążył się policzyć przed złożeniem raportu (routers/reports ustawia tę uwagę zamiast „pending”)
TERRAIN_PENDING_NOTE = "Teren w trakcie liczenia – pełne dane w aplikacji."

# Raport skrócony = dokładnie 2 strony. Gdy tekstu jest za dużo, kolejne stopnie skracają LISTY i zdania (nie czcionkę):
# (znaki punktu werdyktu, punktów, upraw w „Unikaj”, grup „Unikaj”, znaki opisu działania, działań, wierszy rankingu)
COMPACT = [
    {"pt_clip": 150, "pt_n": 4, "avoid_crops": 3, "avoid_groups": 2, "act_clip": 125, "act_n": 3, "rank_n": 5},
    {"pt_clip": 110, "pt_n": 4, "avoid_crops": 2, "avoid_groups": 1, "act_clip": 90, "act_n": 3, "rank_n": 5},
    {"pt_clip": 90, "pt_n": 3, "avoid_crops": 2, "avoid_groups": 1, "act_clip": 70, "act_n": 2, "rank_n": 4},
    {"pt_clip": 70, "pt_n": 3, "avoid_crops": 1, "avoid_groups": 1, "act_clip": 0, "act_n": 2, "rank_n": 3},
]


def render_html(a: AnalysisResponse, ortho: str | None, generated: dt.datetime | None = None,
                report_type: str = "short", compact: int = 0) -> str:
    cp = COMPACT[max(0, min(compact, len(COMPACT) - 1))]
    full_rep = report_type == "full"
    bbox, outline = map_frame(a.parcel.geometria)
    sat_png, sat_style = satellite_overlay(a, bbox) if report_type == "full" else (None, "")
    url = analysis_url(a)
    h = a.history
    ctx = {
        "a": a,
        "generated": generated or dt.datetime.now(dt.timezone.utc),
        # F19: jeden tytuł niezależnie od uprawy
        "title": "Paszport wodny działki",
        "crop_label": CROPS[a.crop].label if a.crop else None,
        "field": a.field_state,
        "field_status": STATUS[a.field_state.status.level] if a.field_state else None,
        "chart_field": Markup(charts.soil_water_chart(a.field_state) or "") if a.field_state else "",
        "field_bar": Markup(charts.bar(a.field_state.soil_water_pct.value, "#2F80C9")) if a.field_state else "",
        "previous_crop_label": CROPS[a.previous_crop].label if a.previous_crop in CROPS else
        ("nie wiem" if a.previous_crop == "nie_wiem" else None),
        "status": STATUS[a.status.level],
        "STATUS": STATUS, "CATEGORY": CATEGORY, "PERMIT_ICON": PERMIT_ICON, "SOURCE_ICON": SOURCE_ICON,
        "CONFIDENCE": CONFIDENCE, "RAIN": RAIN,
        "ortho": ortho, "outline": Markup(outline), "map_side_m": round(bbox[2] - bbox[0]),
        "qr": Markup(qr_svg(url)), "url": url, "url_host": url.split("//", 1)[-1].split("/?")[0],
        "chart_balance": Markup(charts.balance_chart(h) or ""),
        "chart_stress": Markup(charts.stress_chart(h.stress_days_by_year) or ""),
        "chart_precip": Markup(charts.precip_chart(h.monthly_precip) or ""),
        "water_bar": Markup(charts.bar(a.indicators.soil_water_pct.value, "#2F80C9")),
        "terrain": a.terrain,
        "terrain_missing": TERRAIN_PENDING_NOTE if a.terrain_note == TERRAIN_PENDING_NOTE else "Brak danych o terenie dla tej działki.",
        "v": a.verdict, "sug": a.suggestions, "LV": LEVEL, "CAT": CAT_ICON, "KIND": KIND_LABEL,
        "parcel_name": parcel_name(a)[0], "parcel_place": parcel_name(a)[1], "water_actions": water_actions(a),
        "history_labels": history_labels(a),
        "zone_bar": Markup(charts.zone_bar(a.terrain.zones) or "") if a.terrain else "",
        "zones_map": Markup(zones_overlay(a, bbox)),
        "RATING": {"dobrze": ("dobrze", "#5BB37F"), "uwaga": ("uwaga", "#E8B931"), "zle": ("źle", "#C8453B")},
        "css": Markup((HERE / "report.css").read_text(encoding="utf-8")),
        # A5e: raport krótki (4–5 stron) / pełny
        "full": report_type == "full",
        "sat": a.satellite, "sat_png": sat_png, "sat_style": sat_style,
        "hydro": a.hydro if a.hydro is not None and a.hydro.status in ("ok", "none") else None,
        "hydro_label": {"rzeka": "Rzeka", "ciek": "Ciek", "row": "Rów melioracyjny", "kanal": "Kanał",
                        "zbiornik": "Zbiornik wodny"},
        "chart_sat": Markup(charts.satellite_series(a.satellite.series) or "") if a.satellite and a.satellite.series else "",
        "report_label": REPORT_LABEL.get(report_type, REPORT_LABEL["short"]),
        "chart_years_small": Markup(charts.season_bars(a.seasonal_balance_by_year, a.seasonal_balance_mean_mm,
                                                       width=640, height=120) or ""),
        "top_items": top_items(a),
        "recs": a.recommendations if report_type == "full" else a.recommendations[:SHORT_RECS],
        "more_recs": 0 if report_type == "full" else max(0, len(a.recommendations) - SHORT_RECS),
        "limitations": a.reliability.limitations if report_type == "full" else top_limitations(a),
        "more_limits": max(0, len(a.reliability.limitations) - SHORT_LIMITATIONS),
        "weather_until": a.weather_data_until.strftime("%d.%m.%Y") if a.weather_data_until else "brak danych",
        "soil_short": soil_short(a),
        "chart_years": Markup(charts.season_bars(a.seasonal_balance_by_year, a.seasonal_balance_mean_mm) or ""),
        "year_below": bool(a.seasonal_balance_by_year and a.seasonal_balance_mean_mm is not None
                           and a.seasonal_balance_by_year[-1].balance_mm < a.seasonal_balance_mean_mm),
        # F19: układ w stylu paszportu
        "tiles": tiles(a),
        "points": verdict_points(a) if full_rep else verdict_points(a, cp["pt_n"]),
        "cp": cp,
        "now_label": ("W dniu analizy" if a.historical else "Teraz"),
        "now_text": NOW_LABEL.get(a.status.level, ""),
        "long_text": LONG_LABEL.get(a.verdict.level) if a.verdict else None,
        "avoid": avoid_groups(a) if full_rep else avoid_groups(a, cp["avoid_groups"]),
        "pw": price_weather_block(a) if report_type == "full" else None,
        "rank_rows": field_items(a) if report_type == "full" else (top_items(a) or field_items(a))[:cp["rank_n"]],
        "CATT": CAT_TEXT, "PERMIT_TEXT": PERMIT_TEXT,
        "acts": actions(a, None if full_rep else cp["act_n"]),
        "is_ditch": is_ditch,
        "sources_line": sources_line(a, None if report_type == "full" else 3),
        "source_date": source_date,
        "std_limits": STANDARD_LIMITS, "std_limits_short": STANDARD_LIMITS_SHORT,
        "period_text": period_text(a),
        "area_text": area_text(a, short=report_type != "full"),
        "tonnes": tonnes, "zl": zl, "risk_text": risk_text, "yield_text": yield_text, "zl_range": zl_range, "balance_words": balance_words,
        "price_sources": sorted({i.revenue.price_source for i in field_items(a) if i.revenue and i.revenue.price_source}),
        "generated_txt": (generated or dt.datetime.now(dt.timezone.utc)).astimezone().strftime("%d.%m.%Y %H:%M"),
        "app_host": app_url().split("//", 1)[-1],
        # F20: wykresy strony 1 (z danych analizy – stan działki i opady miesięczne)
        "chart_soil_season": Markup(charts.soil_season_chart(a.field_state, low_pct=float(status_cfg()["risk_max_pct"]), height=140) or "") if a.field_state else "",
        "chart_precip_norm": Markup(charts.precip_norm_chart(a.history.monthly_precip, height=140) or ""),
        "soil_sentence": soil_chart_sentence(a),
        "precip_sentence": precip_chart_sentence(a),
    }
    return _env.get_template("report.html").render(**ctx)


def html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML  # import tu: biblioteki systemowe potrzebne tylko do PDF

    return HTML(string=html, base_url=str(HERE)).write_pdf()


def short_pdf(render) -> bytes:
    """Raport skrócony: dokładnie 2 strony. `render(compact)` → HTML; gdy wychodzi więcej stron, kolejny stopień
    skracania list (COMPACT). Zwykle wystarcza pierwszy układ – wtedy jest tylko jedno składanie."""
    from weasyprint import HTML

    doc = None
    for level in range(len(COMPACT)):
        doc = HTML(string=render(level), base_url=str(HERE)).render()
        if len(doc.pages) <= 2:
            break
    return doc.write_pdf()


async def build_pdf(a: AnalysisResponse, report_type: str = "short") -> bytes:
    bbox, _ = map_frame(a.parcel.geometria)
    ortho = await ortho_image(bbox)
    if report_type != "full":
        return await asyncio.to_thread(short_pdf, lambda level: render_html(a, ortho, None, report_type, level))
    html = render_html(a, ortho, report_type=report_type)
    return await asyncio.to_thread(html_to_pdf, html)
