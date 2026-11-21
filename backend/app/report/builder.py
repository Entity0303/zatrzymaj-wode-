"""Raport PDF „Paszport wodny działki” (SPEC 10.2) – WeasyPrint, A4 pionowo. Bez uprawy (A5b-1) – krótszy
raport „Stan wodny działki”: gleba, zapas wody pod pokryciem referencyjnym FAO-56, bilans, retencja.

Treść = wynik normalnej analizy (run_analysis) + mapa działki (ortofotomapa Geoportalu, WMS GetMap przycięta do
obrysu z marginesem) + wykresy SVG (charts.py) + kod QR do analizy online (tylko gdy ustawiony PUBLIC_URL). Raport nie liczy
niczego sam – tylko przedstawia wynik analizy.
"""

import asyncio
import base64
import datetime as dt
import re
from pathlib import Path
from urllib.parse import urlencode

import segno
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from shapely.geometry import shape

from app.analysis.crops import CROPS
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
    "ok": ("Dobrze", "#5BB37F", "#E6F4EA"), "warn": ("Uwaga", "#E8B931", "#FDF4D8"),
    "risk": ("Ryzyko", "#E07B39", "#FCEBDD"), "danger": ("Susza", "#C8453B", "#FBE7E5"),
    "no_data": ("Brak danych", "#B8BDB9", "#F1F2F1"),
}
CATEGORY = {"retencja": ("Retencja", "#2F80C9"), "agrotechnika": ("Agrotechnika", "#8B6B4A"),
            "nawadnianie": ("Nawadnianie", "#2F6B47")}
PERMIT_ICON = {"none": "✓", "maybe": "!", "required": "§"}
SOURCE_ICON = {"ok": "✓", "czesciowo": "⚠", "brak": "✕"}
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


_env.filters.update(num=num, pct=pct, date_pl=date_pl, first_sentence=first_sentence, sentences=sentences)
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


LEVEL = {"ok": ("✓", "#5BB37F"), "warn": ("!", "#E8B931"), "bad": ("✕", "#C8453B"), "info": ("i", "#2F80C9")}
CAT_ICON = {"polecane": ("✓", "#5BB37F"), "mozliwe": ("~", "#E8B931"), "odradzane": ("✕", "#C8453B")}
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
        return settings.public_url.rstrip("/") + "/"
    if a.approximate_area:
        lon, lat = a.approximate_area.center
        return f"{settings.public_url.rstrip('/')}/?{urlencode({'lon': lon, 'lat': lat, 'data': a.analysis_date.isoformat()})}"
    q = {"dzialka": a.parcel.id}
    if a.crop:
        q["uprawa"] = a.crop
    q["data"] = a.analysis_date.isoformat()
    if a.previous_crop:
        q["przedplon"] = a.previous_crop
    return f"{settings.public_url.rstrip('/')}/?{urlencode(q)}"


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


def render_html(a: AnalysisResponse, ortho: str | None, generated: dt.datetime | None = None,
                report_type: str = "short") -> str:
    bbox, outline = map_frame(a.parcel.geometria)
    sat_png, sat_style = satellite_overlay(a, bbox) if report_type == "full" else (None, "")
    url = analysis_url(a)
    h = a.history
    ctx = {
        "a": a,
        "generated": generated or dt.datetime.now(dt.timezone.utc),
        "title": "Paszport wodny działki" if a.crop else "Stan wodny działki",
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
        "qr": Markup(qr_svg(url)) if settings.public_url else "", "url": url, "url_host": url.split("//", 1)[-1].split("/?")[0],
        "chart_balance": Markup(charts.balance_chart(h) or ""),
        "chart_stress": Markup(charts.stress_chart(h.stress_days_by_year) or ""),
        "chart_precip": Markup(charts.precip_chart(h.monthly_precip) or ""),
        "water_bar": Markup(charts.bar(a.indicators.soil_water_pct.value, "#2F80C9")),
        "terrain": a.terrain,
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
        "chart_sat": Markup(charts.satellite_series(a.satellite.series) or "") if a.satellite and a.satellite.series else "",
        "report_label": REPORT_LABEL.get(report_type, REPORT_LABEL["short"]),
        "chart_years_small": Markup(charts.season_bars(a.seasonal_balance_by_year, a.seasonal_balance_mean_mm,
                                                       width=620, height=128) or ""),
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
    }
    return _env.get_template("report.html").render(**ctx)


def html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML  # import tu: biblioteki systemowe potrzebne tylko do PDF

    return HTML(string=html, base_url=str(HERE)).write_pdf()


async def build_pdf(a: AnalysisResponse, report_type: str = "short") -> bytes:
    bbox, _ = map_frame(a.parcel.geometria)
    ortho = await ortho_image(bbox)
    html = render_html(a, ortho, report_type=report_type)
    return await asyncio.to_thread(html_to_pdf, html)
