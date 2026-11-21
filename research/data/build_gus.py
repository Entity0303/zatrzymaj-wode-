"""Buduje gus_variables.csv i gus_yields_woj.csv z GUS BDL API (plony z 1 ha wg województw).

    python research/data/build_gus.py

Każda odpowiedź API jest zapisywana w research/data/gus_raw/ (klucz = URL), więc ponowne
uruchomienie nie odpytuje GUS drugi raz. Zapytania z przerwą 0,6 s, ponowienie przy 429.
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "gus_raw"
BASE = "https://bdl.stat.gov.pl/api/v1/"
YEARS = list(range(2016, 2026))  # ostatnie 10 lat dostępnych w BDL (stan 2026-11-21)
KUJ_POM = "04"

WOJ = {
    "02": "dolnośląskie", "04": "kujawsko-pomorskie", "06": "lubelskie", "08": "lubuskie",
    "10": "łódzkie", "12": "małopolskie", "14": "mazowieckie", "16": "opolskie",
    "18": "podkarpackie", "20": "podlaskie", "22": "pomorskie", "24": "śląskie",
    "26": "świętokrzyskie", "28": "warmińsko-mazurskie", "30": "wielkopolskie",
    "32": "zachodniopomorskie",
}

# crop_id -> (licznik: zmienne „plony” albo „zbiory”, mianownik: zmienne „powierzchnia” albo None, uwagi)
# Gdy mianownik None – zmienna to wprost „plony z 1 ha” [dt].
# Gdy podany – plon = suma zbiorów / suma powierzchni (GUS nie publikuje plonu z ha dla tej grupy).
MAPPING: dict[str, tuple[list[int], list[int] | None, str]] = {
    "zboza_ozime": ([4332], None,
                    "pszenica ogółem jako zastępnik – GUS BDL nie rozdziela form ozimych i jarych; "
                    "pszenica w PL to w ok. 85–90% forma ozima (szac.)"),
    "zboza_jare": ([4344], None,
                   "jęczmień ogółem jako zastępnik – GUS BDL nie rozdziela form; jęczmień w PL to "
                   "głównie forma jara (szac.)"),
    "kukurydza_ziarno": ([47752], None, ""),
    "kukurydza_kiszonka": ([47749], None, "kukurydza na zielonkę – plon zielonej masy (nie suchej masy)"),
    "rzepak": ([4380], None, "rzepak i rzepik razem (ozimy i jary)"),
    "rzepak_jesien": ([4380], None, "ta sama zmienna co rzepak – okres jesienny nie daje osobnego plonu"),
    "ziemniak": ([4368], None, ""),
    "burak_cukrowy": ([4374], None, "plon korzeni"),
    "straczkowe": ([47740], None, "rośliny strączkowe razem (jadalne i pastewne, na ziarno)"),
    "warzywa": ([4398], [4397], "plon wyliczony = zbiory / powierzchnia warzyw gruntowych"),
    "drzewa_owocowe": ([4402], [4401], "plon wyliczony = zbiory / powierzchnia owoców z drzew (wszystkie gatunki)"),
    "krzewy_owocowe": ([1751718, 1751726, 1751730, 1751734, 1751738, 1751746],
                       [1751716, 1751724, 1751728, 1751732, 1751736, 1751744],
                       "plon wyliczony = Σ zbiorów / Σ powierzchni: agrest, porzeczki, maliny, aronia, "
                       "borówki, pozostałe jagodowe (bez truskawek); w BDL od 2021"),
    "truskawki": ([1751742], [1751740], "plon wyliczony = zbiory / powierzchnia; w BDL od 2021"),
    "tyton": ([47768], None, ""),
}
MISSING = {"chmiel": "brak zmiennej plonu, zbiorów ani powierzchni chmielu w BDL na poziomie województw "
                     "(są tylko ceny skupu i płatności ARiMR)"}


def get(path: str, params) -> dict:
    params = list(params.items()) if isinstance(params, dict) else list(params)
    params += [("format", "json"), ("lang", "pl")]
    q = urllib.parse.urlencode(params)
    key = hashlib.sha1((path + "?" + q).encode()).hexdigest()[:16]
    f = RAW / f"{path.replace('/', '_')}_{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    RAW.mkdir(exist_ok=True)
    for attempt in range(5):
        try:
            req = urllib.request.Request(BASE + path + "?" + q,
                                         headers={"User-Agent": "zatrzymaj-wode-research"})
            d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
            f.write_text(json.dumps({"_url": BASE + path + "?" + q,
                                     "_fetched": time.strftime("%Y-%m-%d %H:%M"), **d},
                                    ensure_ascii=False), encoding="utf-8")
            time.sleep(0.6)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"GUS BDL: limit zapytań ({path})")


def series(var_id: int) -> dict[tuple[str, int], float]:
    """(woj_kod, rok) -> wartość; tylko wartości z attrId = 1 (dane jawne)."""
    d = get(f"data/by-variable/{var_id}",
            [("unit-level", 2), ("page-size", 100)] + [("year", y) for y in YEARS])
    out = {}
    for unit in d.get("results", []):
        woj = unit["id"][2:4]
        for v in unit["values"]:
            if v.get("attrId") == 1 and v.get("val") is not None:
                out[(woj, int(v["year"]))] = float(v["val"])
    return out


def meta(var_id: int) -> dict:
    return get(f"variables/{var_id}", {})


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    var_rows, yield_rows = [], []
    for crop, (num, den, note) in MAPPING.items():
        nums = [series(v) for v in num]
        dens = [series(v) for v in den] if den else None
        yields: dict[tuple[str, int], float] = {}
        for woj in WOJ:
            for y in YEARS:
                if dens is None:
                    if (woj, y) in nums[0]:
                        yields[(woj, y)] = nums[0][(woj, y)]
                    continue
                n = [s.get((woj, y)) for s in nums]
                a = [s.get((woj, y)) for s in dens]
                pairs = [(x, z) for x, z in zip(n, a) if x is not None and z is not None and z > 0]
                if pairs and sum(z for _, z in pairs) > 0:
                    yields[(woj, y)] = sum(x for x, _ in pairs) / sum(z for _, z in pairs)
        if not yields:
            MISSING[crop] = "zmienne nie zwracają danych na poziomie województw"
            continue
        for (woj, y), val in sorted(yields.items()):
            yield_rows.append({"crop_id": crop, "woj_kod": woj, "woj_nazwa": WOJ[woj], "rok": y,
                               "plon_dt_ha": round(val, 1)})
        yrs = sorted({y for _, y in yields})
        kp_years = sorted(y for w, y in yields if w == KUJ_POM)
        example = (f"{yields[(KUJ_POM, kp_years[-1])]:.1f} ({kp_years[-1]})" if kp_years else "")
        m = [meta(v) for v in num]
        if den is None:
            name = f"{m[0]['n1']} – {m[0]['n2']} – {m[0]['n3']}"
            vid = str(num[0])
        else:
            md = [meta(v) for v in den]
            name = (" + ".join(x["n1"] for x in m) + " – zbiory / powierzchnia")
            vid = "+".join(map(str, num)) + " / " + "+".join(map(str, den))
            _ = md
        var_rows.append({
            "crop_id": crop, "var_id": vid, "nazwa_zmiennej": name, "jednostka": "dt/ha",
            "poziom": "województwa (unit-level=2)", "lata_od": yrs[0], "lata_do": yrs[-1],
            "przyklad_wartosci": example, "uwagi": note,
        })
        print(f"{crop:20s} {vid:45s} {yrs[0]}–{yrs[-1]}  kuj-pom {example}  ({len(yields)} wartości)")

    with open(HERE / "gus_variables.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(var_rows[0]))
        w.writeheader()
        w.writerows(var_rows)
        for crop, why in MISSING.items():
            w.writerow({"crop_id": crop, "var_id": "", "nazwa_zmiennej": "", "jednostka": "",
                        "poziom": "", "lata_od": "", "lata_do": "", "przyklad_wartosci": "",
                        "uwagi": "BRAK DANYCH W GUS: " + why})
    with open(HERE / "gus_yields_woj.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["crop_id", "woj_kod", "woj_nazwa", "rok", "plon_dt_ha"])
        w.writeheader()
        w.writerows(yield_rows)
    print("brak danych:", MISSING)
    print("wierszy plonów:", len(yield_rows))


if __name__ == "__main__":
    main()
