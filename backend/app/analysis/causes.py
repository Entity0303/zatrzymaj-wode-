"""Przyczyny sytuacji wodnej (SPEC 7.C): czynniki z udziałem (suma 100%) i opisem z liczbą.

Surowe wagi (D37):
- opady – niedobór względem średniej z 10 lat: (średnia − opad) / średnia, gdy opad < średnia,
- parowanie – nadwyżka ET0 względem średniej: (ET0 − średnia) / średnia, gdy ET0 > średnia,
- gleba – mała pojemność wodna: kat. I 0,50; II 0,35; III 0,20; IV 0,10,
- uprawa – zapotrzebowanie w obecnej fazie: 0,15 × Kc w fazach wrażliwych, 0,05 poza nimi,
- teren i spływ (A6, D58) – 0,2 × udział stoków i górek w działce (tam woda z ulewy ucieka / najszybciej przesycha);
  bez analizy NMT – „brak danych”, udział 0.
Udziały = wagi / suma wag (tylko czynniki z danymi), zaokrąglone, suma dokładnie 1.
"""

from app.core.format import num
from app.analysis.facts import Facts
from app.schemas.analysis import Cause, SourceTag

SOIL_WEIGHT = {1: 0.50, 2: 0.35, 3: 0.20, 4: 0.10}
SOIL_WORD = {1: "bardzo mało", 2: "mało", 3: "średnio dużo", 4: "dużo"}
CROP_WEIGHT_PER_KC = 0.15
CROP_WEIGHT_OFF = 0.05
TERRAIN_WEIGHT = 0.2


def _fmt(v: float) -> str:
    return num(v, 0)


def build_causes(f: Facts) -> list[Cause]:
    raw: list[tuple[float, Cause]] = []
    start = f.get("season_start_txt") or "początku sezonu"
    obl = SourceTag(kind="obliczenia", source="NASA POWER")

    p, pm = f.get("precip_mm"), f.get("precip_mean_mm")
    if p is not None and pm:
        w = max(0.0, (pm - p) / pm)
        desc = f"od {start} spadło {_fmt(p)} mm, zwykle {_fmt(pm)} mm"
        raw.append((w, Cause(factor="opady", title="Mało opadów" if w > 0 else "Opady w normie lub powyżej",
                             share=0, description=desc, source_tag=obl)))
    e, em = f.get("et0_mm"), f.get("et0_mean_mm")
    if e is not None and em:
        w = max(0.0, (e - em) / em)
        desc = f"parowanie od {start}: {_fmt(e)} mm, zwykle {_fmt(em)} mm"
        raw.append((w, Cause(factor="parowanie", title="Duże parowanie" if w > 0 else "Parowanie w normie",
                             share=0, description=desc,
                             source_tag=SourceTag(kind="obliczenia", source="NASA POWER, ET0 FAO-56"))))
    cat, wod = f.get("soil_category"), f.get("wod_mm")
    if cat in SOIL_WEIGHT and wod is not None:
        desc = f"kat. {f.get('soil_category_roman')}, zmieści ok. {_fmt(wod)} mm wody – {SOIL_WORD[cat]}"
        raw.append((SOIL_WEIGHT[cat], Cause(factor="gleba", title="Gleba", share=0, description=desc,
                                            source_tag=SourceTag(kind="pomiar", source="IUNG-PIB"))))
    if f.get("kc") is not None and f.get("phase_label"):
        if f.get("sensitive"):
            w = CROP_WEIGHT_PER_KC * f["kc"]
            etc = num(f["etc_mm_day"], 1) if f.get("etc_mm_day") else None
            use = f", zużycie wody ok. {etc} mm dziennie" if etc else ""
            kc = num(f["kc"], 2)
            desc = f"{f['crop_label'].lower()} – {f['phase_label']}{use} (Kc {kc})"
        else:
            w = CROP_WEIGHT_OFF
            desc = f"{f['crop_label'].lower()} – {f['phase_label']}: małe zapotrzebowanie na wodę"
        raw.append((w, Cause(factor="uprawa", title="Wymagania uprawy", share=0, description=desc,
                             source_tag=SourceTag(kind="szacunek_modelu", source="FAO-56 (Kc)"))))

    runoff = f.get("terrain_runoff_pct")
    if runoff is not None:
        wet = f.get("terrain_wet_pct") or 0
        desc = f"stoki i górki na {runoff}% działki – tu woda z ulewy spływa lub szybko przesycha"
        if wet:
            desc += f"; obniżenia, gdzie zbiera się woda {wet}%"
        raw.append((TERRAIN_WEIGHT * runoff / 100, Cause(factor="teren", title="Teren i spływ", share=0, description=desc,
                                                          source_tag=SourceTag(kind="pomiar", source="NMT GUGiK"))))

    total = sum(w for w, _ in raw)
    causes: list[Cause] = []
    if total > 0:
        shares = [round(w / total, 2) for w, _ in raw]
        if shares:
            k = max(range(len(shares)), key=lambda j: shares[j])
            shares[k] = round(shares[k] + 1.0 - sum(shares), 2)  # suma dokładnie 1
        for (w, c), s in zip(raw, shares):
            causes.append(c.model_copy(update={"share": max(0.0, s)}))
    causes.sort(key=lambda c: -c.share)
    if runoff is not None:
        return causes
    causes.append(Cause(factor="teren", title="Teren i spływ", share=0.0,
                        description="brak danych (analiza terenu w przygotowaniu)",
                        source_tag=SourceTag(kind="brak_danych", source="NMT GUGiK")))
    return causes
