"""Wykresy SVG do raportu PDF – generowane w Pythonie (bez bibliotek), kolory z SPEC 2.2.

Każda funkcja zwraca gotowy znacznik <svg> (wstawiany do szablonu bez escapowania) albo None, gdy brak danych.
"""

import datetime as dt
from html import escape

from app.schemas.analysis import BandPoint, History, MonthlyPrecip, SeriesPoint, YearStress

C = {
    "brand": "#2F6B47", "water": "#2F80C9", "water_soft": "#E3F0FB", "danger": "#C8453B", "warn": "#E8B931",
    "muted": "#5F6B64", "border": "#E3DED4", "text": "#1E2A23", "nodata": "#B8BDB9", "earth": "#8B6B4A",
}
MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]
FONT = 'font-family="Inter, sans-serif"'


def _num(v: float) -> str:
    return f"{v:.0f}".replace("-", "−")


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = max(hi - lo, 1.0)
    raw = span / n
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000) if s >= raw)
    start = (lo // step) * step
    out, v = [], start
    while v <= hi + 1e-9:
        if v >= lo - 1e-9:
            out.append(v)
        v += step
    return out


def balance_chart(h: History, width: int = 680, height: int = 190) -> str | None:
    """Bilans wody narastająco: pasmo min–max z 10 lat, średnia (przerywana), bieżący sezon (gruba linia)."""
    band: list[BandPoint] = [b for b in h.balance_band if b.min is not None and b.max is not None]
    cur: list[SeriesPoint] = [p for p in h.balance_cumulative if p.value is not None]
    if not band and not cur:
        return None
    dates = [b.date for b in band] + [p.date for p in cur]
    d0, d1 = min(dates), max(dates)
    vals = [b.min for b in band] + [b.max for b in band] + [p.value for p in cur] + [0.0]
    lo, hi = min(vals), max(vals)
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
        color = C["danger"] if (h.balance_deviation_mm or 0) < 0 else C["brand"]
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.4"/>')
        parts.append(f'<circle cx="{x(last.date):.1f}" cy="{y(last.value):.1f}" r="3.5" fill="{color}"/>')
        parts.append(f'<text x="{min(x(last.date) + 6, width - 60):.1f}" y="{y(last.value) - 6:.1f}" fill="{color}" font-weight="600">{_num(last.value)} mm</text>')
    parts.append(f'<text x="{pad_l}" y="{pad_t - 2}" fill="{C["muted"]}">mm</text>')
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
