"""Wspólny format liczb i dat w tekstach dla rolnika (A14): przecinek dziesiętny, spacja tysięcy, minus typograficzny,
rozsądne zaokrąglenie, daty DD.MM.RRRR. Jedno miejsce – analiza, werdykt, rekomendacje, ograniczenia, zdania satelity
i wody (raport PDF może z niego korzystać przez `app.core.format`).
"""

from __future__ import annotations

import datetime as dt
import math

NBSP = " "   # spacja tysięcy (nierozdzielająca – liczba nie łamie się w tekście)
MINUS = "−"


def num(x: float | int | None, decimals: int | None = None, thousands_from: int = 10_000) -> str:
    """0.858 → „0,86”; 4.5 → „4,5”; 22183 → „22 183”; −0.24 → „−0,24”. `decimals=None` – automatycznie:
    |x| < 1 → 2 miejsca, < 10 → 1, reszta – całe. Spacja tysięcy od `thousands_from` (zwyczaj PL: od 10 000)."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "–"
    v = float(x)
    if decimals is None:
        a = abs(v)
        decimals = 0 if a >= 10 or v == int(v) else 1 if a >= 1 else 2
    s = f"{abs(v):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if abs(v) >= thousands_from:
        whole = f"{int(whole):,}".replace(",", NBSP)
    out = whole + ("," + frac if frac else "")
    if v < 0 and out.strip("0,") != "":
        out = MINUS + out
    return out


def plural(n: int, one: str, few: str, many: str) -> str:
    """Forma liczebnika po polsku (A18): 1 dzień, 2–4 dni, 5 dni, 22 dni… – samo słowo, bez liczby.
    Np. plural(n, "dzień", "dni", "dni"), plural(n, "zdjęcie", "zdjęcia", "zdjęć")."""
    n = abs(int(n))
    if n == 1:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def days(n: int) -> str:
    """„1 dzień”, „3 dni”, „12 dni”."""
    return f"{n} {plural(n, 'dzień', 'dni', 'dni')}"


def zl(x: float | None) -> str:
    """Kwota w złotych ze spacją tysięcy od 1 000 (A18 – jednolicie z objętościami): 2100 → „2 100 zł”."""
    return "–" if x is None else f"{num(x, 0, thousands_from=1000)} zł"


def volume_m3(x: float | None) -> str:
    """Objętość wody po ludzku (orientacyjnie): 380 → „380 m³”, 1546 → „1 500 m³”… ≥ 10 000 → „22 tys. m³”."""
    if x is None or not math.isfinite(float(x)):
        return "–"
    v = float(x)
    if v >= 10_000:
        return f"{num(round(v / 1000))} tys. m³"
    if v >= 1000:
        return f"{int(round(v, -2)):,}".replace(",", NBSP) + " m³"
    if v >= 100:
        return f"{int(round(v, -1))} m³"
    return f"{num(v, 0)} m³"


def rain_area_ha(volume: float, rain_mm: float = 20.0) -> float:
    """Ile hektarów pola daje taką objętość wody w ulewie `rain_mm` (1 mm na 1 ha = 10 m³)."""
    return volume / (rain_mm * 10.0)


def date_pl(d: dt.date | dt.datetime | str | None) -> str:
    """Data DD.MM.RRRR (z obiektu albo ISO)."""
    if d is None:
        return "–"
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    return f"{d:%d.%m.%Y}"
