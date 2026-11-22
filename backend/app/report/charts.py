"""Wykresy SVG do raportu PDF – generowane w Pythonie (bez bibliotek), kolory z SPEC 2.2.

Każda funkcja zwraca gotowy znacznik <svg> (wstawiany do szablonu bez escapowania) albo None, gdy brak danych.
"""

import datetime as dt
from html import escape

from app.schemas.analysis import BandPoint, FieldState, History, MonthlyPrecip, SeriesPoint, YearStress

C = {
    "brand": "#2F6B47", "water": "#2F80C9", "water_soft": "#E3F0FB", "danger": "#C8453B", "warn": "#E8B931",
    "muted": "#5F6B64", "border": "#E3DED4", "text": "#1E2A23", "nodata": "#B8BDB9", "earth": "#8B6B4A",
}
MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]
FONT = 'font-family="Liberation Sans, Arial, DejaVu Sans, sans-serif"'


def _num(v: float) -> str:
    return f"{v:.0f}".replace("-", "−")


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = max(hi - lo, 1.0)
    raw = span / n
    # większe zakresy (np. cena rzepaku > 3000 zł/t) – kolejne „okrągłe” kroki; bez domyślnej wartości next() rzucał
    # StopIteration i raport pełny kończył się błędem 500
    step = next((s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000) if s >= raw),
                10 ** len(str(int(raw))))
    start = (lo // step) * step
    out, v = [], start
    while v <= hi + 1e-9:
        if v >= lo - 1e-9:
            out.append(v)
        v += step
    return out


def balance_chart(h: History, width: int = 680, height: int = 190) -> str | None:
    """Bilans wody narastająco: pasmo min–max z 10 lat, średnia (przerywana), bieżący sezon (gruba linia)."""
    return band_chart(h.balance_band, h.balance_cumulative, "mm", (h.balance_deviation_mm or 0) < 0, width, height)


def soil_water_chart(f: FieldState, width: int = 680, height: int = 170) -> str | None:
    """Stan działki: woda dostępna w profilu (%) od 1 listopada na tle tego samego okresu w 10 latach."""
    r = f.soil_water.rank
    below = bool(r and r.of_years and r.lower_years < r.of_years / 2)
    return band_chart(f.series_band, f.series, "%", below, width, height, fixed=(0.0, 100.0))


def band_chart(band_in: list[BandPoint], cur_in: list[SeriesPoint], unit: str, below: bool, width: int = 680,
               height: int = 190, fixed: tuple[float, float] | None = None) -> str | None:
    """Pasmo min–max z 10 lat, średnia (przerywana), bieżący okres (gruba linia; czerwona, gdy gorzej niż zwykle)."""
    band: list[BandPoint] = [b for b in band_in if b.min is not None and b.max is not None]
    cur: list[SeriesPoint] = [p for p in cur_in if p.value is not None]
    if not band and not cur:
        return None
    dates = [b.date for b in band] + [p.date for p in cur]
    d0, d1 = min(dates), max(dates)
    vals = [b.min for b in band] + [b.max for b in band] + [p.value for p in cur] + [0.0]
    lo, hi = fixed or (min(vals), max(vals))
    pad_l, pad_r, pad_t, pad_b = 46, 12, 12, 26
    w, hh = width - pad_l - pad_r, height - pad_t - pad_b
    days = max((d1 - d0).days, 1)

    def x(d: dt.date) -> float:
        return pad_l + w * (d - d0).days / days

    def y(v: float) -> float:
        return pad_t + hh * (hi - v) / max(hi - lo, 1.0)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" {FONT} font-size="10">']
    for t in _ticks(lo, hi):
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="{C["border"]}" stroke-width="{1.2 if t == 0 else 0.6}"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{y(t) + 3:.1f}" text-anchor="end" fill="{C["muted"]}">{_num(t)}</text>')
    m = dt.date(d0.year, d0.month, 1)
    while m <= d1:
        if m >= d0:
            parts.append(f'<line x1="{x(m):.1f}" x2="{x(m):.1f}" y1="{pad_t}" y2="{pad_t + hh}" stroke="{C["border"]}" stroke-width="0.5"/>')
            parts.append(f'<text x="{x(m) + 2:.1f}" y="{height - 8}" fill="{C["muted"]}">{MONTHS[m.month - 1]}</text>')
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    if band:
        upper = " ".join(f"{x(b.date):.1f},{y(b.max):.1f}" for b in band)
        lower = " ".join(f"{x(b.date):.1f},{y(b.min):.1f}" for b in reversed(band))
        parts.append(f'<polygon points="{upper} {lower}" fill="{C["water_soft"]}" stroke="none"/>')
        mean = [b for b in band if b.mean is not None]
        if mean:
            pts = " ".join(f"{x(b.date):.1f},{y(b.mean):.1f}" for b in mean)
            parts.append(f'<polyline points="{pts}" fill="none" stroke="{C["water"]}" stroke-width="1.2" stroke-dasharray="4 3"/>')
    if cur:
        pts = " ".join(f"{x(p.date):.1f},{y(p.value):.1f}" for p in cur)
        last = cur[-1]
        color = C["danger"] if below else C["brand"]
        label = f"{_num(last.value)}{unit}" if unit == "%" else f"{_num(last.value)} {unit}"
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.4"/>')
        parts.append(f'<circle cx="{x(last.date):.1f}" cy="{y(last.value):.1f}" r="3.5" fill="{color}"/>')
        parts.append(f'<text x="{min(x(last.date) + 6, width - 60):.1f}" y="{max(y(last.value) - 6, pad_t + 8):.1f}" fill="{color}" font-weight="600">{label}</text>')
    parts.append(f'<text x="{pad_l}" y="{pad_t - 2}" fill="{C["muted"]}">{unit}</text>')
    parts.append("</svg>")
    return "".join(parts)


def stress_chart(years: list[YearStress], width: int = 330, height: int = 170) -> str | None:
    """Dni stresu wodnego w kolejnych sezonach; bieżący wyróżniony, brak danych – szary napis."""
    if not years:
        return None
    years = sorted(years, key=lambda ys: ys.year)
    pad_l, pad_b, pad_t = 26, 22, 14
    vals = [ys.stress_days for ys in years if ys.stress_days is not None]
    top = max(vals + [5])
    bw = (width - pad_l - 6) / len(years)
    hh = height - pad_b - pad_t
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" {FONT} font-size="9">']
    for t in _ticks(0, top, 3):
        yy = pad_t + hh * (1 - t / top)
        parts.append(f'<line x1="{pad_l}" x2="{width - 4}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{C["border"]}" stroke-width="0.6"/>')
        parts.append(f'<text x="{pad_l - 4}" y="{yy + 3:.1f}" text-anchor="end" fill="{C["muted"]}">{_num(t)}</text>')
    for i, ys in enumerate(years):
        x0 = pad_l + i * bw + bw * 0.15
        label = f"’{str(ys.year)[2:]}"
        parts.append(f'<text x="{x0 + bw * 0.35:.1f}" y="{height - 8}" text-anchor="middle" fill="{C["muted"]}">{label}</text>')
        if ys.stress_days is None:
            parts.append(f'<text x="{x0 + bw * 0.35:.1f}" y="{pad_t + hh - 4:.1f}" text-anchor="middle" fill="{C["nodata"]}">b.d.</text>')
            continue
        bh = hh * ys.stress_days / top
        color = C["danger"] if ys.is_current else C["earth"]
        parts.append(f'<rect x="{x0:.1f}" y="{pad_t + hh - bh:.1f}" width="{bw * 0.7:.1f}" height="{bh:.1f}" rx="2" fill="{color}" opacity="{1 if ys.is_current else 0.55}"/>')
        if ys.is_current or ys.stress_days == max(vals):
            parts.append(f'<text x="{x0 + bw * 0.35:.1f}" y="{pad_t + hh - bh - 3:.1f}" text-anchor="middle" fill="{C["text"]}">{ys.stress_days}</text>')
    parts.append("</svg>")
    return "".join(parts)


def precip_chart(months: list[MonthlyPrecip], width: int = 330, height: int = 170) -> str | None:
    """Opad miesięczny: bieżący rok (niebieski) i średnia z 10 lat (szary)."""
    ms = [m for m in months if m.current_mm is not None or m.mean_mm is not None]
    if not ms:
        return None
    pad_l, pad_b, pad_t = 26, 22, 14
    top = max([m.current_mm or 0 for m in ms] + [m.mean_mm or 0 for m in ms] + [10])
    bw = (width - pad_l - 6) / len(ms)
    hh = height - pad_b - pad_t
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" {FONT} font-size="9">']
    for t in _ticks(0, top, 3):
        yy = pad_t + hh * (1 - t / top)
        parts.append(f'<line x1="{pad_l}" x2="{width - 4}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{C["border"]}" stroke-width="0.6"/>')
        parts.append(f'<text x="{pad_l - 4}" y="{yy + 3:.1f}" text-anchor="end" fill="{C["muted"]}">{_num(t)}</text>')
    for i, m in enumerate(ms):
        x0 = pad_l + i * bw + bw * 0.1
        for j, (v, color) in enumerate(((m.mean_mm, C["nodata"]), (m.current_mm, C["water"]))):
            if v is None:
                continue
            bh = hh * v / top
            parts.append(f'<rect x="{x0 + j * bw * 0.4:.1f}" y="{pad_t + hh - bh:.1f}" width="{bw * 0.38:.1f}" height="{bh:.1f}" fill="{color}"/>')
        parts.append(f'<text x="{x0 + bw * 0.4:.1f}" y="{height - 8}" text-anchor="middle" fill="{C["muted"]}">{MONTHS[m.month - 1]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def zone_bar(zones, width: int = 520, height: int = 16) -> str | None:
    """Pasek udziałów stref terenu (górka / stok / płasko / dołek) w kolorach stref (A6)."""
    zs = [z for z in zones if z.share_pct > 0]
    if not zs:
        return None
    total = sum(z.share_pct for z in zs) or 1.0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height + 14}" '
             f'viewBox="0 0 {width} {height + 14}" {FONT} font-size="9">']
    x = 0.0
    for z in zs:
        w = width * z.share_pct / total
        parts.append(f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="{height}" fill="{z.color}"/>')
        x += w
    parts.append("</svg>")
    return "".join(parts)


def zones_svg(shapes: list[tuple[str, list[list[tuple[float, float]]]]], width: int, height: int) -> str:
    """Strefy terenu na mapce (pierścienie już w pikselach) – nakładka pod obrysem działki."""
    polys = "".join(
        f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in ring)}" fill="{color}" fill-opacity="0.72" '
        f'stroke="{color}" stroke-width="0.6"/>' for color, rings in shapes for ring in rings
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'class="outline">{polys}</svg>')


def outline_svg(rings: list[list[tuple[float, float]]], width: int, height: int, color: str = "#FFD84D") -> str:
    """Obrys działki (współrzędne już w pikselach) – nakładka na ortofotomapę."""
    polys = "".join(
        f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in ring)}" fill="none" stroke="{color}" '
        f'stroke-width="3" stroke-linejoin="round"/>' for ring in rings
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'class="outline">{polys}</svg>')


def bar(value: float | None, color: str, width: int = 140, height: int = 8) -> str:
    """Pasek 0–100 (np. woda w glebie)."""
    v = 0 if value is None else max(0.0, min(100.0, value))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<rect width="{width}" height="{height}" rx="{height / 2}" fill="{C["border"]}"/>'
            f'<rect width="{width * v / 100:.1f}" height="{height}" rx="{height / 2}" fill="{escape(color)}"/></svg>')


def season_bars(years, mean_mm: float | None, width: int = 680, height: int = 190) -> str | None:
    """„Na tle 10 lat” (A5e): słupek na każdy rok – ile wody zostało od początku sezonu do tego samego dnia
    (spadło minus wyparowało, mm); bieżący rok wyróżniony, linia przerywana = średnia z lat porównawczych.
    `years` – lista SeasonalBalanceYear (year, balance_mm, current) – te same liczby co w API."""
    ys = [y for y in years if y.balance_mm is not None]
    if len(ys) < 2:
        return None
    vals = [y.balance_mm for y in ys] + ([mean_mm] if mean_mm is not None else []) + [0.0]
    lo, hi = min(vals), max(vals)
    pad = max(10.0, 0.08 * (hi - lo))
    lo, hi = lo - pad, hi + pad
    # F20: miejsce na wartość pod najniższym słupkiem i rok; F24: prawy margines na podpis średniej
    pad_l, pad_r, pad_t, pad_b = 40, (62 if mean_mm is not None else 8), 16, 34
    hh = height - pad_t - pad_b

    def y_of(v: float) -> float:
        return pad_t + hh * (hi - v) / (hi - lo)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
             f'{FONT} font-size="10">']
    for t in _ticks(lo, hi, 4):
        yy = y_of(t)
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{C["border"]}" '
                     f'stroke-width="0.6"/>')
        parts.append(f'<text x="{pad_l - 5}" y="{yy + 3:.1f}" text-anchor="end" fill="{C["muted"]}">{_num(t)}</text>')
    y0 = y_of(0.0)
    parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="{C["muted"]}" stroke-width="0.9"/>')
    bw = (width - pad_l - pad_r) / len(ys)
    below_mean = mean_mm is not None and ys[-1].balance_mm < mean_mm
    for i, y in enumerate(ys):
        x = pad_l + i * bw + bw * 0.18
        top, bot = sorted((y_of(y.balance_mm), y0))
        # F19: bieżący rok – kolor ryzyka pod średnią, kolor wody nad nią; poprzednie lata szare (czytelne także w druku cz-b)
        color = ("#E07B39" if below_mean else C["water"]) if y.current else "#C9CCC6"
        parts.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw * 0.64:.1f}" height="{max(bot - top, 0.8):.1f}" '
                     f'fill="{color}" rx="1.5"/>')
        # F20: dodatnie – nad słupkiem; ujemne – pod słupkiem, ale zawsze nad osią lat (z odstępem)
        # F24: mała wartość (słupek niższy niż 3 px) – tuż przy osi zera
        lab_y = (min(top, y0) - 3) if y.balance_mm >= 0 else min(max(bot, y0) + 10, height - 19)
        weight = ' font-weight="700"' if y.current else ""
        parts.append(f'<text x="{x + bw * 0.32:.1f}" y="{lab_y:.1f}" text-anchor="middle" font-size="8.5" '
                     f'fill="{C["text"] if y.current else C["muted"]}"{weight}>{_num(y.balance_mm)}</text>')
        parts.append(f'<text x="{x + bw * 0.32:.1f}" y="{height - 6}" text-anchor="middle" '
                     f'fill="{C["text"] if y.current else C["muted"]}"{weight}>{y.year}</text>')
    if mean_mm is not None:
        ym = y_of(mean_mm)
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{ym:.1f}" y2="{ym:.1f}" stroke="{C["water"]}" '
                     f'stroke-width="1.4" stroke-dasharray="5 3"/>')
        tx = width - pad_r + 4  # F24: podpis po prawej stronie linii, poza słupkami
        parts.append(f'<text x="{tx}" y="{ym - 1:.1f}" fill="{C["water"]}" font-weight="600">średnia</text>')
        parts.append(f'<text x="{tx}" y="{ym + 10:.1f}" fill="{C["water"]}" font-weight="600">{_num(mean_mm)} mm</text>')
    parts.append("</svg>")
    return "".join(parts)


def satellite_series(points, width: int = 680, height: int = 150) -> str | None:
    """Szereg Sentinel-2 (A11): NDVI (zielona) i NDMI (niebieska) w czasie; oś −0,4…1."""
    pts = [p for p in points if p.ndvi is not None]
    if len(pts) < 2:
        return None
    pad_l, pad_r, pad_t, pad_b = 30, 8, 10, 20
    d0, d1 = pts[0].date, pts[-1].date
    span = max((d1 - d0).days, 1)
    lo, hi = -0.4, 1.0

    def xy(d, v):
        return (pad_l + (width - pad_l - pad_r) * (d - d0).days / span,
                pad_t + (height - pad_t - pad_b) * (hi - v) / (hi - lo))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
             f'{FONT} font-size="9">']
    for t in (-0.4, 0.0, 0.5, 1.0):
        y = xy(d0, t)[1]
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y:.1f}" y2="{y:.1f}" stroke="{C["border"]}" stroke-width="0.6"/>')
        lab = f"{t:.1f}".replace(".", ",").replace("-", "−")
        parts.append(f'<text x="{pad_l - 4}" y="{y + 3:.1f}" text-anchor="end" fill="{C["muted"]}">{lab}</text>')
    for key, color in (("ndvi", "#3F8E4E"), ("ndmi", C["water"])):
        seq = [(p.date, getattr(p, key)) for p in pts if getattr(p, key) is not None]
        if len(seq) < 2:
            continue
        path = " ".join(f"{'M' if i == 0 else 'L'}{xy(d, v)[0]:.1f},{xy(d, v)[1]:.1f}" for i, (d, v) in enumerate(seq))
        parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"/>')
        for d, v in seq:
            x, y = xy(d, v)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="{color}"/>')
    seen = set()
    for p in pts:
        key = (p.date.year, p.date.month)
        if key in seen:
            continue
        seen.add(key)
        x = xy(p.date, lo)[0]
        parts.append(f'<text x="{x:.1f}" y="{height - 6}" text-anchor="middle" fill="{C["muted"]}">{MONTHS[p.date.month - 1]}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ── F20: wykresy na stronę 1 raportu skróconego (czytelne czarno-biało: wzory i rodzaje linii, nie tylko kolor) ──

_HATCH = ('<defs><pattern id="{id}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
          '<rect width="5" height="5" fill="{bg}"/><line x1="0" y1="0" x2="0" y2="5" stroke="{fg}" stroke-width="1.6"/>'
          '</pattern></defs>')


def soil_season_chart(f: FieldState, low_pct: float = 50.0, width: int = 340, height: int = 165) -> str | None:
    """„Zapas wody w glebie w tym sezonie”: bieżący rok (gruba ciągła linia, %) na tle pasma 10 lat (min–max, jasnoszare)
    i średniej z 10 lat (przerywana); strefa „mało wody” (< low_pct – próg statusu „mało wody”, 40%, jasnoczerwona, kreskowana). Oś Y 0–100%."""
    band = [b for b in f.series_band if b.min is not None and b.max is not None]
    cur = [p for p in f.series if p.value is not None]
    if len(cur) < 2 and len(band) < 2:
        return None
    dates = [b.date for b in band] + [p.date for p in cur]
    d0, d1 = min(dates), max(dates)
    pad_l, pad_r, pad_t, pad_b = 38, 8, 10, 22
    w, hh = width - pad_l - pad_r, height - pad_t - pad_b
    days = max((d1 - d0).days, 1)

    def x(d: dt.date) -> float:
        return pad_l + w * (d - d0).days / days

    def y(v: float) -> float:
        return pad_t + hh * (100 - max(0.0, min(100.0, v))) / 100

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
             f'{FONT} font-size="12.5">', _HATCH.format(id="lowz", bg="#FBE7E5", fg="#F2C4BE")]
    parts.append(f'<rect x="{pad_l}" y="{y(low_pct):.1f}" width="{w}" height="{y(0) - y(low_pct):.1f}" fill="url(#lowz)"/>')
    parts.append(f'<text x="{width - pad_r - 3}" y="{y(0) - 4:.1f}" text-anchor="end" fill="#8F2A21">mało wody</text>')
    for t in (0, 50, 100):
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="{C["border"]}" stroke-width="0.8"/>')
        parts.append(f'<text x="{pad_l - 5}" y="{y(t) + 4:.1f}" text-anchor="end" fill="{C["muted"]}">{t}%</text>')
    m = dt.date(d0.year, d0.month, 1)
    step = 2 if (d1 - d0).days > 200 else 1
    k = 0
    while m <= d1:
        if m >= d0:
            if k % step == 0:
                parts.append(f'<text x="{x(m) + 2:.1f}" y="{height - 6}" fill="{C["muted"]}">{MONTHS[m.month - 1]}</text>')
            parts.append(f'<line x1="{x(m):.1f}" x2="{x(m):.1f}" y1="{pad_t}" y2="{pad_t + hh}" stroke="{C["border"]}" stroke-width="0.5"/>')
            k += 1
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    if band:
        upper = " ".join(f"{x(b.date):.1f},{y(b.max):.1f}" for b in band)
        lower = " ".join(f"{x(b.date):.1f},{y(b.min):.1f}" for b in reversed(band))
        parts.append(f'<polygon points="{upper} {lower}" fill="#E2E4E1" stroke="none"/>')
        mean = [b for b in band if b.mean is not None]
        if mean:
            pts = " ".join(f"{x(b.date):.1f},{y(b.mean):.1f}" for b in mean)
            parts.append(f'<polyline points="{pts}" fill="none" stroke="#5F6B64" stroke-width="1.4" stroke-dasharray="5 3"/>')
    if cur:
        pts = " ".join(f"{x(p.date):.1f},{y(p.value):.1f}" for p in cur)
        last = cur[-1]
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#1E2A23" stroke-width="2.6"/>')
        parts.append(f'<circle cx="{x(last.date):.1f}" cy="{y(last.value):.1f}" r="3.6" fill="#1E2A23"/>')
        tx = min(x(last.date) + 6, width - pad_r - 36)
        parts.append(f'<text x="{tx:.1f}" y="{max(y(last.value) - 7, pad_t + 11):.1f}" font-weight="700" fill="#1E2A23" '
                     f'stroke="#FFFFFF" stroke-width="3" paint-order="stroke">{_num(last.value)}%</text>')
    parts.append("</svg>")
    return "".join(parts)


def precip_norm_chart(months: list[MonthlyPrecip], width: int = 340, height: int = 165, low: float = 0.7) -> str | None:
    """„Opady w miesiącach vs norma”: słupek opadu bieżącego roku (mm), pozioma kreska normy z 10 lat; miesiące
    poniżej `low` × normy – kolor ryzyka i kreskowanie (czytelne w druku cz-b)."""
    if len([m for m in months if m.current_mm is not None]) < 2:
        return None
    ms = list(months)  # F24: miesiąc bez pełnych danych zostaje na osi – oznaczony „?”, nie jako 0
    pad_l, pad_r, pad_t, pad_b = 34, 6, 12, 22
    top = max([m.current_mm or 0 for m in ms] + [m.mean_mm or 0 for m in ms] + [10]) * 1.08
    bw = (width - pad_l - pad_r) / len(ms)
    hh = height - pad_t - pad_b
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
             f'{FONT} font-size="12.5">', _HATCH.format(id="lowp", bg="#F6D2B8", fg="#E07B39")]
    for t in _ticks(0, top, 3):
        yy = pad_t + hh * (1 - t / top)
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{C["border"]}" stroke-width="0.7"/>')
        parts.append(f'<text x="{pad_l - 4}" y="{yy + 4:.1f}" text-anchor="end" fill="{C["muted"]}">{_num(t)}</text>')
    for i, m in enumerate(ms):
        x0 = pad_l + i * bw + bw * 0.18
        bwi = bw * 0.64
        if m.current_mm is None:
            parts.append(f'<rect x="{x0:.1f}" y="{pad_t:.1f}" width="{bwi:.1f}" height="{hh:.1f}" fill="none" stroke="#9AA19C" '
                         f'stroke-width="0.8" stroke-dasharray="3 2"/>')
            parts.append(f'<text x="{x0 + bwi / 2:.1f}" y="{pad_t + hh / 2:.1f}" text-anchor="middle" fill="#555F58">?</text>')
            parts.append(f'<text x="{x0 + bwi / 2:.1f}" y="{height - 6}" text-anchor="middle" fill="{C["muted"]}">{MONTHS[m.month - 1]}</text>')
            continue
        dry = m.mean_mm is not None and m.mean_mm > 0 and m.current_mm < low * m.mean_mm
        bh = hh * m.current_mm / top
        fill = "url(#lowp)" if dry else C["water"]
        stroke = "#E07B39" if dry else C["water"]
        parts.append(f'<rect x="{x0:.1f}" y="{pad_t + hh - bh:.1f}" width="{bwi:.1f}" height="{max(bh, 0.8):.1f}" fill="{fill}" '
                     f'stroke="{stroke}" stroke-width="0.8"/>')
        if m.mean_mm is not None:
            ym = pad_t + hh * (1 - m.mean_mm / top)
            parts.append(f'<line x1="{x0 - bw * 0.08:.1f}" x2="{x0 + bwi + bw * 0.08:.1f}" y1="{ym:.1f}" y2="{ym:.1f}" '
                         f'stroke="#1E2A23" stroke-width="2"/>')
        parts.append(f'<text x="{x0 + bwi / 2:.1f}" y="{height - 6}" text-anchor="middle" fill="{C["muted"]}">{MONTHS[m.month - 1]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def price_weather_chart(rows: list[dict], dry_years: list[int], width: int = 660, height: int = 210) -> str | None:
    """F32: „Ceny i pogoda na tle lat” (porównanie regionalne): słupki = opad IV–IX [mm] (lata najsuchsze – kolor ryzyka
    i kreskowanie), linia ciągła = cena skupu [zł/t, prawa oś], linia przerywana = plon w regionie [t/ha]."""
    rows = [r for r in rows if r.get("precip_mm") is not None or r.get("price_pln_t") is not None or r.get("yield_t_ha") is not None]
    if len(rows) < 2:
        return None
    pad_l, pad_r, pad_t, pad_b = 36, 44, 14, 22
    w, hh = width - pad_l - pad_r, height - pad_t - pad_b
    rain_max = max([r["precip_mm"] or 0 for r in rows] + [100]) * 1.08
    price_max = max([r["price_pln_t"] or 0 for r in rows] + [500]) * 1.08
    yield_max = max([r["yield_t_ha"] or 0 for r in rows] + [1]) * 1.25
    bw = w / len(rows)

    def cx(i: int) -> float:
        return pad_l + bw * (i + 0.5)

    def y(v: float, top: float) -> float:
        return pad_t + hh * (1 - v / top)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
             f'{FONT} font-size="10">', _HATCH.format(id="pwdry", bg="#F6D2B8", fg="#E07B39")]
    for t in _ticks(0, rain_max, 3):
        yy = y(t, rain_max)
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{C["border"]}" stroke-width="0.6"/>')
        parts.append(f'<text x="{pad_l - 4}" y="{yy + 3:.1f}" text-anchor="end" fill="{C["water"]}">{_num(t)}</text>')
    for t in _ticks(0, price_max, 3):
        parts.append(f'<text x="{width - pad_r + 4}" y="{y(t, price_max) + 3:.1f}" fill="{C["text"]}">{_num(t)}</text>')
    parts.append(f'<text x="{pad_l - 4}" y="{pad_t - 4}" text-anchor="end" fill="{C["water"]}">mm</text>')
    parts.append(f'<text x="{width - pad_r + 4}" y="{pad_t - 4}" fill="{C["text"]}">zł/t</text>')
    dry = set(dry_years)
    for i, r in enumerate(rows):
        if r.get("precip_mm") is not None:
            top = y(r["precip_mm"], rain_max)
            is_dry = r["year"] in dry
            parts.append(f'<rect x="{cx(i) - bw * 0.3:.1f}" y="{top:.1f}" width="{bw * 0.6:.1f}" height="{max(pad_t + hh - top, 0.8):.1f}" '
                         f'fill="{"url(#pwdry)" if is_dry else C["water"]}" stroke="{"#E07B39" if is_dry else C["water"]}" '
                         f'stroke-width="0.7" opacity="0.9"/>')
        parts.append(f'<text x="{cx(i):.1f}" y="{height - 6}" text-anchor="middle" fill="{C["muted"]}">{r["year"]}</text>')
    for key, top, color, dash, width_ in (("yield_t_ha", yield_max, C["brand"], ' stroke-dasharray="5 3"', 1.8),
                                          ("price_pln_t", price_max, C["text"], "", 2.0)):
        pts = [(cx(i), y(r[key], top)) for i, r in enumerate(rows) if r.get(key) is not None]
        if len(pts) >= 2:
            parts.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="none" stroke="{color}" '
                         f'stroke-width="{width_}"{dash}/>')
        for a, b in pts:
            parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="2.2" fill="{"#FFFFFF" if dash else color}" stroke="{color}" stroke-width="1.2"/>')
    parts.append("</svg>")
    return "".join(parts)

