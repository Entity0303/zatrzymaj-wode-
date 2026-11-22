"""Werdykt działki (A5b-2b, D68): 4–6 prostych zdań z liczbami – gleba, opady, teren, uprawy, woda (+ wybrana uprawa)
i jedno zdanie ogólne. Szablony i progi: rules/verdict.yaml. Deterministycznie: te same dane → te same zdania.
Wejście = wyniki, które analiza już policzyła (etykieta gleby, pogoda z 10 lat, teren, ranking, rekomendacje, status).
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from app.core.format import num, rain_area_ha, volume_m3
from app.analysis.et0 import DailyWeather
from app.analysis.soil_label import SoilProfile
from app.schemas.analysis import (
    CropSuggestions,
    OverallStatus,
    Recommendation,
    Terrain,
    Verdict,
    VerdictCrop,
    VerdictStatement,
)

RULES = Path(__file__).parent / "rules" / "verdict.yaml"
NOTE = ("Zdania policzone z danych tej działki (gleba, pogoda z 10 lat, teren, symulacja upraw) według stałych "
        "szablonów – bez modelu językowego; te same dane dają te same zdania.")
LEVEL_ORDER = {"ok": 0, "warn": 1, "bad": 2}
RATING_LEVEL = {"dobrze": "ok", "uwaga": "warn", "zle": "bad"}
STATUS_LEVEL = {"ok": "ok", "warn": "warn", "risk": "bad", "danger": "bad"}


@lru_cache
def cfg() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))["verdict"]


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " i " + items[-1]


def _cap(t: str) -> str:
    return t[:1].upper() + t[1:] if t else t


# ── gleba ───────────────────────────────────────────────────────────────────────────────────


def soil_statement(prof: SoilProfile, wod_mm: float | None) -> VerdictStatement:
    c = cfg()["soil"]
    group = prof.group
    if group == "lekka" and wod_mm is not None and wod_mm >= cfg()["thresholds"]["soil_light_warn_wod_mm"]:
        group = "lekka_warn"  # A14: lżejsza gleba, ale WOD działki przeciętny – jak w modelu i rankingu
    rule = c.get(group) or c["nieznana"]
    wod = "brak danych" if wod_mm is None else f"{round(wod_mm)}"
    nums: dict = {"wod_mm": None if wod_mm is None else round(wod_mm), "grupa": prof.group,
                  "srednia_kategoria": prof.mean_category, "zrodlo": prof.source}
    if prof.two_soils:
        a, b = prof.parts[0], prof.parts[1]
        text = c["two_soils"].format(a_pct=round(100 * a.share), a_name=a.name, b_pct=round(100 * b.share), b_name=b.name)
        tail = c["two_soils_tail"].get(group)
        if tail:
            text += " " + tail.format(wod=wod)
        nums.update(udzial_a=round(100 * a.share), udzial_b=round(100 * b.share))
    else:
        opis = prof.describe() if prof.parts else prof.label
        text = rule["text"].format(opis=opis, wod=wod)
    return VerdictStatement(kind="gleba", level=rule["level"], text=text, numbers=nums)


# ── opady (KBW) ─────────────────────────────────────────────────────────────────────────────


def precip_stats(w: DailyWeather, last: date, years: int = 10) -> dict | None:
    """Średnie opady roczne i IV–IX z ostatnich `years` pełnych lat kalendarzowych przed datą analizy oraz liczba lat
    z klimatycznym bilansem wodnym maj–czerwiec poniżej progu (opad − ET0, ta sama pogoda co w analizie)."""
    thr = cfg()["thresholds"]["kbw_may_june_deficit_mm"]
    y_last = last.year - 1
    rows = []
    for y in range(y_last - years + 1, y_last + 1):
        yr = (w.dates >= np.datetime64(f"{y}-01-01")) & (w.dates <= np.datetime64(f"{y}-12-31"))
        if yr.sum() < 360 or np.isnan(w.precip[yr]).mean() > 0.1:
            continue
        se = (w.dates >= np.datetime64(f"{y}-04-01")) & (w.dates <= np.datetime64(f"{y}-09-30"))
        mj = (w.dates >= np.datetime64(f"{y}-05-01")) & (w.dates <= np.datetime64(f"{y}-06-30"))
        kbw = float(np.nansum(w.precip[mj] - w.et0[mj]))
        rows.append((y, float(np.nansum(w.precip[yr])), float(np.nansum(w.precip[se])), kbw))
    if len(rows) < 5:
        return None
    return {"years": len(rows), "year_mm": round(float(np.mean([r[1] for r in rows]))),
            "season_mm": round(float(np.mean([r[2] for r in rows]))),
            "deficit_years": int(sum(r[3] < thr for r in rows)),
            "deficit_list": [r[0] for r in rows if r[3] < thr], "first": rows[0][0], "last": rows[-1][0]}


def precip_statement(st: dict | None, measured: bool = False) -> VerdictStatement | None:
    if st is None:
        return None
    c, t = cfg()["precip"], cfg()["thresholds"]
    level = ("bad" if st["deficit_years"] >= t["deficit_years_bad"] else
             "warn" if st["deficit_years"] >= t["deficit_years_warn"] else "ok")
    low = st["year_mm"] < t["precip_low_ratio"] * t["precip_norm_year_mm"]
    key = level
    if low and level == "ok":
        level, key = "warn", "low"
    elif low and level == "warn":
        key = "low"
    text = c[key].format(**st)
    norm = t["precip_norm_year_mm"]
    if measured:  # A7: opad ze stacji IMGW – porównanie z normą wprost
        ratio = st["year_mm"] / norm
        key_n = "norm_low" if ratio < 0.95 else "norm_high" if ratio > 1.05 else "norm_same"
        text += c[key_n].format(norm_mm=norm)
    else:  # neutralnie – NASA POWER zawyża opad względem IMGW (D68)
        text += c["norm_tail"].format(norm_mm=norm)
    nums = {k: st[k] for k in ("year_mm", "season_mm", "deficit_years", "years", "first", "last")}
    nums["norma_mm"] = norm
    nums["zrodlo_opadu"] = "IMGW" if measured else "NASA POWER"
    return VerdictStatement(kind="opady", level=level, text=text, numbers=nums)


# ── teren ───────────────────────────────────────────────────────────────────────────────────


def terrain_statement(t: Terrain | None, pending: bool = False) -> VerdictStatement:
    if t is None and pending:  # A9: NMT liczony w tle
        return VerdictStatement(kind="teren", level="info", text=cfg()["terrain_pending"], numbers={})
    if t is None:
        return VerdictStatement(kind="teren", level="warn", text=cfg()["terrain_missing"], numbers={})
    min_pct = cfg()["thresholds"]["terrain_zone_min_pct"]
    big = sorted((z for z in t.zones if z.sentence and z.share_pct >= min_pct), key=lambda z: -z.share_pct)[:2]
    if not big:
        big = sorted((z for z in t.zones if z.sentence), key=lambda z: -z.share_pct)[:1]
    level = max((RATING_LEVEL[z.rating] for z in big), key=LEVEL_ORDER.get, default="ok")
    text = " ".join(z.sentence for z in big)
    if t.depressions_count and t.largest_depression and t.largest_depression.volume_m3:
        vol = t.largest_depression.volume_m3
        text += f" Jest tu zagłębienie bez odpływu – zmieści orientacyjnie ok. {volume_m3(vol)} wody"
        ha = rain_area_ha(vol)
        text += (f" (tyle, ile spada na ok. {num(round(ha, -1) if ha >= 20 else round(ha))} ha w ulewie 20 mm)."
                 if ha >= 2 else ".")
    return VerdictStatement(kind="teren", level=level, text=text,
                            numbers={z.key: round(z.share_pct) for z in t.zones})


# ── uprawy ──────────────────────────────────────────────────────────────────────────────────


def _bad_reason(item, light: bool) -> str:
    if item.rotation.status == "naruszenie":
        return "plodozmian"
    if item.soil_suitability == "nieodpowiednia":
        if not light and (item.reason or "").startswith("Mapa glebowo-rolnicza"):
            return "gleba_kompleks"  # A15: o „nie siej” decyduje kompleks z mapy, nie opis gleby wyżej
        return "gleba_lekka" if light else "gleba"
    return "woda"


def crops_statement(sug: CropSuggestions | None, light: bool):
    if sug is None or not sug.groups:
        return None, [], []
    c, t = cfg()["crops"], cfg()["thresholds"]
    field = [i for g in sug.groups if g.key == "polowe" for i in g.items]
    good = [i for i in field if i.category == "polecane"][: t["crops_good_max"]]
    best_kind = "best"
    if len(good) < t["crops_good_min"]:
        good = (good + [i for i in field if i.category == "mozliwe"])[: max(t["crops_good_min"], len(good))]
        best_kind = "best_possible" if good else best_kind
    pop = {k: n for n, k in enumerate(cfg()["popular"])}
    bad = sorted((i for i in field if i.category == "odradzane"), key=lambda i: pop.get(i.crop_id, 99))
    acc, gen = cfg()["accusative"], cfg()["genitive"]
    best = _join([acc.get(i.crop_id, i.label.lower()) for i in good])
    text = ""
    bad_out = []
    if bad:  # najpierw czego nie siać, potem co siać (jak mówi doradca)
        by_reason: dict[str, list] = {}
        for i in bad:
            by_reason.setdefault(_bad_reason(i, light), []).append(i)
        main_reason, items = max(by_reason.items(), key=lambda kv: len(kv[1]))
        shown = items[: t["crops_bad_max"]]
        text = c["bad"].format(bad=_join([gen.get(i.crop_id, i.label.lower()) for i in shown]),
                               reason=c["reasons"][main_reason])
        if good:
            text += " " + (c["instead"] if best_kind == "best" else c["best_possible"]).format(instead=best, best=best)
        for reason, its in by_reason.items():
            bad_out += [VerdictCrop(crop_id=i.crop_id, label=i.label, reason=c["reasons"][reason]) for i in its]
        bad_out.sort(key=lambda v: pop.get(v.crop_id, 99))
    elif good:
        text = c[best_kind].format(best=best)
    wheat = next((i for i in field if i.crop_id == "pszenica_ozima"), None)
    if wheat and wheat.category == "polecane":
        loss = round(100 * (1 - wheat.relative_yield_weak))
        tpl = c["wheat_dry_year"] if loss <= c["wheat_small_loss_max_pct"] else c["wheat_dry_year_big"]
        text += tpl.format(year=wheat.weak_year, loss=loss)
    if not bad:
        text += c["none_bad"]
    n_good, n_bad = len([i for i in field if i.category == "polecane"]), len(bad)
    level = "bad" if n_good == 0 and n_bad >= 3 else "warn" if n_good < 2 or n_bad >= 3 else "ok"
    best_rev = next((i for i in good if getattr(i, "revenue", None) is not None), None)
    if best_rev is not None:  # A12: tylko gdy jest cena skupu
        r = best_rev.revenue
        text += (f" Przychód z {num(r.for_area_ha, 2)} ha ({best_rev.label.lower()}): ok. {num(r.typical_zl, 0)} zł "
                 f"w typowym roku, ok. {num(r.weak_year_zl, 0)} zł w słabym (ceny skupu GUS).")
    st = VerdictStatement(kind="uprawy", level=level, text=text.strip(),
                          numbers={"polecane": n_good, "odradzane": n_bad, "mozliwe": len(field) - n_good - n_bad})
    return st, [VerdictCrop(crop_id=i.crop_id, label=i.label) for i in good], bad_out


# ── woda (działania) ────────────────────────────────────────────────────────────────────────


def water_statement(recs: list[Recommendation], hydro=None) -> VerdictStatement:
    """Lista działań – bez oceny: poziom zawsze „info” (A5b-2c); A9: zdanie o rowie / cieku, gdy jest w okolicy."""
    st = _water_statement(recs)
    if hydro is not None and getattr(hydro, "status", None) == "ok" and hydro.features:
        f = next((x for x in hydro.features if x.kind in ("row", "kanal")), hydro.features[0])
        from app.analysis.hydro import KIND_LABEL, _dist_txt

        extra = f" {KIND_LABEL[f.kind]} {_dist_txt(f.distance_m)}" + (", w kierunku odpływu wody." if f.toward_outflow
                                                                     else ".")
        st = st.model_copy(update={"text": st.text + extra})
    return st


def _water_statement(recs: list[Recommendation]) -> VerdictStatement:
    c, t = cfg()["water"], cfg()["thresholds"]
    # retencja przed agrotechniką; pewne (bez ostrzeżenia) przed tymi „do sprawdzenia na miejscu”
    ret = sorted((r for r in recs if r.category in ("retencja", "agrotechnika")),
                 key=lambda r: (r.category != "retencja", bool(r.warning), not r.in_panel))[: t["water_actions_max"]]
    level = "info"
    if not ret:
        return VerdictStatement(kind="woda", level=level, text=c["none"], numbers={})
    acts = [r.title[:1].lower() + r.title[1:] for r in ret]
    return VerdictStatement(kind="woda", level=level, text=c["text"].format(actions="; ".join(acts)),
                            numbers={"dzialania": len(acts)})


# ── nagłówek i całość ───────────────────────────────────────────────────────────────────────


def _match(cond: dict, lv: dict[str, str], wet: float, dry: float) -> bool:
    for k, v in cond.items():
        if k == "uprawy_not":
            if lv.get("uprawy") == v:
                return False
        elif k == "bad_count_gte":
            if sum(x == "bad" for x in lv.values()) < v:
                return False
        elif k == "wet_pct_gte":
            if wet < v:
                return False
        elif k == "dry_pct_gte":
            if dry < v:
                return False
        else:
            allowed = v if isinstance(v, list) else [v]
            if lv.get(k) not in allowed:
                return False
    return True


def plants_statement(sat) -> VerdictStatement | None:
    """A11: pozycja „rosliny” – tylko gdy jest zdjęcie satelitarne (zdanie z wartości NDVI / NDMI i porównania)."""
    if sat is None or getattr(sat, "status", None) != "ok" or not sat.sentence:
        return None
    return VerdictStatement(kind="rosliny", level=sat.level or "info", text=sat.sentence,
                            numbers={"ndvi": sat.ndvi, "ndmi": sat.ndmi, "data": sat.date.isoformat() if sat.date else None,
                                     "ndvi_rok_temu": sat.last_year.ndvi if sat.last_year else None})


def build(prof: SoilProfile, wod_mm: float | None, w: DailyWeather, last: date, terrain: Terrain | None,
          sug: CropSuggestions | None, recs: list[Recommendation], field_status: OverallStatus | None,
          chosen: tuple[str, str, OverallStatus, bool] | None = None, measured_precip: bool = False,
          satellite=None, terrain_pending: bool = False, hydro=None) -> Verdict:
    sts = [soil_statement(prof, wod_mm)]
    p = precip_statement(precip_stats(w, last), measured_precip)
    if p:
        sts.append(p)
    sts.append(terrain_statement(terrain, terrain_pending))
    plants = plants_statement(satellite)
    if plants:
        sts.append(plants)
    crops, good, bad = crops_statement(sug, prof.group == "lekka")
    if crops:
        sts.append(crops)
    sts.append(water_statement(recs, hydro))
    if chosen:
        label, phase, status, off = (*chosen, False)[:4]
        tpl = cfg()["chosen_crop_off"] if off else cfg()["chosen_crop"]
        sts.append(VerdictStatement(kind="uprawa_wybrana", level=STATUS_LEVEL.get(status.level, "warn"),
                                    text=tpl.format(crop=label, phase=phase, headline=status.headline),
                                    numbers={"wynik": status.score, "poza_sezonem": 1 if off else 0}))
    # „rosliny” – bez wpływu na nagłówek; teren liczony w tle (info) – jak brak danych (warn), jak przed A9
    lv = {s.kind: ("warn" if s.level == "info" else s.level) for s in sts if s.kind in ("gleba", "opady", "teren", "uprawy")}
    wet = terrain.zone_share_pct.get("mokry_dolek", 0.0) if terrain else 0.0
    dry = terrain.zone_share_pct.get("sucha_gorka", 0.0) if terrain else 0.0
    headline = next(h["text"] for h in cfg()["headlines"] if _match(h["if"], lv, wet, dry))
    level = max(lv.values(), key=LEVEL_ORDER.get, default="warn")
    if level == "bad" and lv.get("gleba") == "ok" and sum(v == "bad" for v in lv.values()) == 1:
        level = "warn"
    return Verdict(headline=headline, level=level, statements=sts, crops_good=good, crops_bad=bad, note=NOTE)
