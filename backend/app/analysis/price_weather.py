"""A28: „Ceny i pogoda na tle lat” – porównanie REGIONALNE (województwo albo cała Polska; nie działka, wieś ani powiat).

Dla każdego roku: cena skupu GUS (zł/t), średni plon GUS (t/ha) i średnia suma opadów IV–IX ze stacji IMGW regionu.
Wniosek liczony z danych: lata najsuchsze (dolne 25% opadów) na tle pozostałych – średnie odchylenie plonu i ceny
od trendu (Theil–Sen), bo plony i ceny rosną z roku na rok.
To zestawienie lat, nie przyczyna: cenę kształtuje rynek krajowy i światowy. Dane statyczne (pliki w repo) – wynik
zapamiętany w pamięci procesu. Stacje przypisujemy do województwa po NAJBLIŻSZYM środku województwa (w repo nie ma
granic województw ani kodów TERYT stacji) – to przybliżenie, opisane w `sources`.
"""

from __future__ import annotations

import csv
import math
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.analysis.approx_area import VOIVODESHIP_CENTERS, nearest_voivodeship
from app.sources import imgw

DATA = Path(__file__).parents[1] / "data"
PRICES_CSV = DATA / "prices" / "gus_prices.csv"
PRICE_VARS_CSV = DATA / "prices" / "gus_price_variables.csv"
YIELDS_CSV = DATA / "crops" / "gus_yields_woj.csv"

FIRST_YEAR = 2013
MIN_YEARS = 6            # mniej wspólnych lat – same dane, bez wniosku
DRY_SHARE = 0.25         # „najsuchsze” = dolne 25% lat wg opadów IV–IX
MIN_COVERAGE = 0.90      # stacja liczy się w roku, gdy ma ≥ 90% dni sezonu
SEASON = ((4, 1), (9, 30))
PL = "PL"
NOTE = "To porównanie lat w regionie, nie przyczyna – cenę kształtuje rynek krajowy i światowy."
NOTE_2022 = " Skok cen w 2022 r. wynikał z sytuacji na rynkach światowych (wojna w Ukrainie), nie z pogody."
NO_PRICE_NOTE = "brak cen skupu GUS dla tej uprawy"

# produkt GUS → (mianownik, dopełniacz do zdania „plon …”)
PRODUCT_WORDS = {
    "pszenica": ("Pszenica", "pszenicy"), "żyto": ("Żyto", "żyta"), "jęczmień": ("Jęczmień", "jęczmienia"),
    "owies": ("Owies", "owsa"), "pszenżyto": ("Pszenżyto", "pszenżyta"), "kukurydza": ("Kukurydza na ziarno", "kukurydzy"),
    "ziemniaki": ("Ziemniaki", "ziemniaków"), "rzepak": ("Rzepak", "rzepaku"), "buraki": ("Buraki cukrowe", "buraków cukrowych"),
}


def _plain(text: str) -> str:
    """Bez polskich znaków i wielkich liter – do porównania nazw z zapytania."""
    t = unicodedata.normalize("NFKD", text.strip().lower().replace("ł", "l"))
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def region_key(region: str | None) -> str | None:
    """„PL” / „polska” → PL; nazwa województwa (z polskimi znakami lub bez) albo kod TERYT („20”) → nazwa; inaczej None."""
    r = _plain(region or "")
    if r in ("pl", "polska", "poland", "00"):
        return PL
    names = {_plain(n): n for n in VOIVODESHIP_CENTERS}
    if r in names:
        return names[r]
    codes = {code: name for (_c, name), code in _woj_codes().items()}
    return codes.get(r.zfill(2)) if r.isdigit() else None


@lru_cache
def _woj_codes() -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    with open(YIELDS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[("woj", row["woj_nazwa"])] = row["woj_kod"]
    return out


@lru_cache
def products() -> dict[str, dict]:
    """produkt GUS → {crops: [kody upraw], label, genitive}; oraz odwrotnie: kod uprawy → produkt (`by_crop`)."""
    out: dict[str, dict] = {}
    with open(PRICE_VARS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            p = row["produkt"]
            label, gen = PRODUCT_WORDS.get(p, (p.capitalize(), p))
            out[p] = {"crops": [c for c in row["uprawy"].split(";") if c], "label": label, "genitive": gen}
    return out


def product_for(crop: str | None) -> str | None:
    """Kod uprawy („pszenica_ozima”, „zboza_ozime”) albo nazwa produktu („pszenica”) → produkt z cenami GUS."""
    c = (crop or "").strip()
    for p, info in products().items():
        if c in info["crops"] or _plain(c) == _plain(p):
            return p
    return None


@lru_cache
def load_prices() -> dict[tuple[str, str], dict[int, float]]:
    """(produkt, region) → {rok: zł/t}; region = PL albo nazwa województwa. W pliku zł/dt."""
    out: dict[tuple[str, str], dict[int, float]] = {}
    with open(PRICES_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            region = PL if row["poziom"] == "polska" else row["nazwa"]
            try:
                out.setdefault((row["produkt"], region), {})[int(row["rok"])] = round(float(row["zl_dt"]) * 10, 1)
            except ValueError:
                continue
    return out


@lru_cache
def load_yields() -> dict[tuple[str, str], dict[int, float]]:
    """(kod uprawy, region) → {rok: t/ha}. Plik ma województwa (dt/ha); Polska = średnia z województw z danymi."""
    out: dict[tuple[str, str], dict[int, float]] = {}
    with open(YIELDS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                out.setdefault((row["crop_id"], row["woj_nazwa"]), {})[int(row["rok"])] = float(row["plon_dt_ha"]) / 10
            except ValueError:
                continue
    crops = {c for c, _ in out}
    for c in crops:
        by_year: dict[int, list[float]] = {}
        for (cc, _woj), ys in list(out.items()):
            if cc == c:
                for y, v in ys.items():
                    by_year.setdefault(y, []).append(v)
        out[(c, PL)] = {y: sum(v) / len(v) for y, v in by_year.items()}
    return {k: {y: round(v, 2) for y, v in ys.items()} for k, ys in out.items()}


def season_precip(st: imgw.Store, station_idx: np.ndarray, years: range) -> dict[int, tuple[float, int]]:
    """Średnia suma opadów IV–IX [mm] ze stacji `station_idx` → {rok: (mm, liczba stacji)}. Stacja liczy się w roku,
    gdy ma ≥ 90% dni sezonu (suma uzupełniona proporcjonalnie do pełnego sezonu); rok bez pełnego sezonu w magazynie
    albo bez żadnej takiej stacji – pomijany."""
    out: dict[int, tuple[float, int]] = {}
    if len(station_idx) == 0:
        return out
    for y in years:
        a = (np.datetime64(f"{y}-{SEASON[0][0]:02d}-{SEASON[0][1]:02d}", "D") - st.start).astype(int)
        b = (np.datetime64(f"{y}-{SEASON[1][0]:02d}-{SEASON[1][1]:02d}", "D") - st.start).astype(int)
        if a < 0 or b >= st.days:
            continue
        seg = st.data[a:b + 1][:, station_idx].astype(float)
        seg[seg < 0] = np.nan
        days = seg.shape[0]
        valid = (~np.isnan(seg)).sum(axis=0)
        ok = valid >= MIN_COVERAGE * days
        if not ok.any():
            continue
        sums = np.nansum(seg[:, ok], axis=0) / 10.0 * (days / valid[ok])
        out[y] = (round(float(sums.mean()), 1), int(ok.sum()))
    return out


@lru_cache
def _station_regions(path_mtime: tuple[str, float] | None) -> tuple[str, ...]:
    st = imgw.store()
    return tuple(nearest_voivodeship(float(lo), float(la)) for lo, la in zip(st.lon, st.lat)) if st else ()


def region_precip(region: str, years: range) -> dict[int, tuple[float, int]]:
    st = imgw.store()
    if st is None:
        return {}
    regs = _station_regions((st.built, float(st.days)))
    idx = np.arange(len(regs)) if region == PL else np.array([i for i, r in enumerate(regs) if r == region], dtype=int)
    return season_precip(st, idx, years)


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100


def _diff_words(pct: float, lower: str, higher: str, similar: str) -> str:
    r = round(abs(pct))
    return similar if r < 1 else f"średnio o {r}% {lower if pct < 0 else higher}"


def theil_sen(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Trend odporny na pojedyncze lata (Theil–Sen, jak w A16): nachylenie = mediana nachyleń par lat, wyraz wolny =
    mediana (y − nachylenie · x). Mniej niż 4 punkty – None."""
    if len(points) < 4:
        return None
    slopes = [(y2 - y1) / (x2 - x1) for k, (x1, y1) in enumerate(points) for x2, y2 in points[k + 1:] if x2 != x1]
    if not slopes:
        return None
    slope = float(np.median(slopes))
    return slope, float(np.median([y - slope * x for x, y in points]))


def add_deviations(rows: list[dict]) -> None:
    """A28b: do każdego roku dopisuje odchylenie plonu i ceny od trendu, % (`yield_dev_pct`, `price_dev_pct`) – plony
    i ceny rosną z roku na rok, więc porównujemy „o ile powyżej / poniżej typowego dla tamtych lat”, nie surowe liczby."""
    for key, out in (("yield_t_ha", "yield_dev_pct"), ("price_pln_t", "price_dev_pct")):
        trend = theil_sen([(r["year"], r[key]) for r in rows if r[key] is not None])
        for r in rows:
            base = trend[0] * r["year"] + trend[1] if trend else None
            r[out] = round((r[key] / base - 1) * 100, 1) if r[key] is not None and base and base > 0 else None


def summarize(rows: list[dict], crop_gen: str, where: str) -> tuple[list[int], str | None]:
    """Lata najsuchsze (dolne 25% opadów) na tle pozostałych → (lata, zdanie): średnie ODCHYLENIE od trendu plonu i ceny
    w latach najsuchszych minus w pozostałych. Mniej niż MIN_YEARS pełnych lat – bez zdania."""
    full = [r for r in rows if r["precip_mm"] is not None and r.get("price_dev_pct") is not None
            and r.get("yield_dev_pct") is not None]
    if len(full) < MIN_YEARS:
        return [], None
    k = max(1, math.ceil(len(full) * DRY_SHARE))
    dry = sorted(full, key=lambda r: r["precip_mm"])[:k]
    dry_years = sorted(r["year"] for r in dry)
    rest = [r for r in full if r["year"] not in dry_years]
    mean = lambda rs, key: sum(r[key] for r in rs) / len(rs)  # noqa: E731
    dy = mean(dry, "yield_dev_pct") - mean(rest, "yield_dev_pct")
    dp = mean(dry, "price_dev_pct") - mean(rest, "price_dev_pct")
    yield_txt = _diff_words(dy, "niższy", "wyższy", "podobny")
    price_txt = _diff_words(dp, "niższa", "wyższa", "podobna").replace("średnio ", "")
    typical = " od typowego dla tamtych lat" if round(abs(dy)) >= 1 else " do typowego dla tamtych lat"
    joiner = ", a" if (dy < 0) != (dp < 0) or round(abs(dy)) < 1 or round(abs(dp)) < 1 else " i"
    years_txt = ", ".join(str(y) for y in dry_years)
    return dry_years, (f"W najsuchszych latach ({years_txt}) plon {crop_gen} {where} był {yield_txt}{typical}"
                       f"{joiner} cena skupu {price_txt}.")


def region_phrase(region: str) -> tuple[str, str]:
    """(etykieta, „w województwie podlaskim” / „w Polsce”)."""
    if region == PL:
        return "Polska", "w Polsce"
    loc = region[:-2] + "im" if region.endswith("ie") else region
    return f"woj. {region}", f"w województwie {loc}"


def build(region: str, crop: str, to_year: int, *, prices=None, yields=None, precip=None) -> dict:
    """Odpowiedź endpointu. `region` – klucz z `region_key`; `prices` / `yields` / `precip` – tylko do testów."""
    label, where = region_phrase(region)
    product = product_for(crop)
    if product is None:
        from app.analysis.crops import ALL_CROPS

        c = ALL_CROPS.get(crop)
        return {"region_label": label, "crop_label": c.label if c else crop, "unavailable": True, "note_pl": NO_PRICE_NOTE,
                "years": [], "dry_years": [], "summary_pl": None, "sources": []}
    info = products()[product]
    years = range(FIRST_YEAR, to_year)
    prices = load_prices() if prices is None else prices
    yields = load_yields() if yields is None else yields
    precip = region_precip(region, years) if precip is None else precip
    price_by_year = prices.get((product, region), {})
    # plon: uprawa z zapytania, jeśli ma plony GUS; inaczej pierwsza uprawa produktu z plonami
    yield_crop = next((c for c in [crop, *info["crops"]] if (c, region) in yields), None)
    yield_by_year = yields.get((yield_crop, region), {}) if yield_crop else {}
    rows = [{"year": y,
             "precip_mm": precip[y][0] if y in precip else None,
             "price_pln_t": price_by_year.get(y),
             "yield_t_ha": yield_by_year.get(y)} for y in years]
    add_deviations(rows)
    dry_years, summary = summarize(rows, info["genitive"], where)
    note = NOTE + (NOTE_2022 if any(r["year"] == 2022 and r["price_pln_t"] is not None for r in rows) else "")
    stations = sorted({n for _mm, n in precip.values()})
    sources = [
        f"GUS BDL – ceny skupu ({product}), średnie roczne, {label}",
        f"GUS BDL – plony z 1 ha ({yield_crop or 'brak'})" + (", Polska = średnia z województw" if region == PL else f", {label}"),
        "IMGW-PIB – dobowe opady stacji, suma IV–IX" + (
            f"; {stations[0]}–{stations[-1]} stacji w roku" if stations else "; brak stacji z pełnym sezonem")
        + ("" if region == PL else "; stacje przypisane do województwa po najbliższym środku województwa (przybliżenie)"),
    ]
    return {"region_label": label, "crop_label": info["label"], "unavailable": False, "years": rows, "dry_years": dry_years,
            "summary_pl": summary, "note_pl": note, "sources": sources}


@lru_cache(maxsize=512)
def cached(region: str, crop: str, to_year: int) -> dict:
    return build(region, crop, to_year)


def clear_cache() -> None:
    cached.cache_clear()
    _station_regions.cache_clear()
