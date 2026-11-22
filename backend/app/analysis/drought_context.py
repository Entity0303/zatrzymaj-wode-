"""Tło suszowe z Europejskiego Obserwatorium Suszy (A26): łączny wskaźnik suszy (CDI), anomalia wilgotności gleby
i ryzyko dla rolnictwa w okolicy działki – jako niezależne potwierdzenie naszej oceny.

Dekada: wskaźniki EDO są dekadowe (1–10, 11–20, 21–koniec miesiąca). Bierzemy OSTATNIĄ ZAKOŃCZONĄ dekadę przed datą
analizy (tylko dane sprzed daty); gdy usługa nie ma jeszcze danych dla tej dekady (oba piksele CDI przezroczyste) –
bierzemy wcześniejszą, najwyżej `MAX_BACK` dekad wstecz. Dwie najnowsze dekady pytamy naraz (jedna dekada to ok. 1–3 s,
a świeża dekada bywa jeszcze nieopublikowana) – inaczej nie zmieścilibyśmy się w 8 s. Wynik zawsze podaje dekadę.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

from app.core.http import SourceError, log_source_error
from app.schemas.drought import AgriRisk, Cdi, DroughtContext, SoilMoistureAnomaly
from app.sources import edo

MAX_BACK = 3
TOTAL_TIMEOUT_S = 8.0
UNAVAILABLE_NOTE = "Europejskie Obserwatorium Suszy chwilowo nie odpowiada – tło suszowe pokażemy przy kolejnej próbie."
NO_DATA_NOTE = "Europejskie Obserwatorium Suszy nie ma danych dla tego miejsca i terminu."
CDI_LABEL = {"brak": "brak suszy", "obserwacja": "obserwacja (początek niedoboru opadów)",
             "ostrzeżenie": "ostrzeżenie przed suszą", "alarm": "alarm suszowy", "regeneracja": "regeneracja po suszy"}
SMA_LABEL = {"w_normie": "w normie", "sucho": "sucho", "bardzo_sucho": "bardzo sucho", "wilgotno": "wilgotno"}
RISK_LABEL = {"brak": "bez wskazanego ryzyka", "niskie": "niskie", "srednie": "średnie", "wysokie": "wysokie"}
# nasz stopień (status.level) → nazwa ze słownika i czy oznacza niedobór wody
OUR = {"ok": ("W normie", False), "warn": ("Uwaga", False), "risk": ("Mało wody", True), "danger": ("Bardzo mało wody", True)}
OUR_BY_NAME = {name.lower(): key for key, (name, _dry) in OUR.items()}
EDO_DRY = {"ostrzeżenie", "alarm"}


def decade_start(d: date) -> date:
    return d.replace(day=1 if d.day <= 10 else 11 if d.day <= 20 else 21)


def decade_end(start: date) -> date:
    if start.day == 21:
        nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1)
    return start.replace(day=start.day + 9)


def previous_decade(start: date) -> date:
    return decade_start(start - timedelta(days=1))


def last_complete_decade(analysis_date: date) -> date:
    """Pierwszy dzień ostatniej dekady, która skończyła się PRZED datą analizy."""
    return previous_decade(decade_start(analysis_date))


def decade_label(start: date) -> str:
    end = decade_end(start)
    return f"dekada {start.day}–{end:%d.%m.%Y}"


def our_level(our_status: str | None) -> str | None:
    """`ok|warn|risk|danger` albo nagłówek statusu („Bardzo mało wody w glebie”) → klucz stopnia."""
    if not our_status:
        return None
    s = our_status.strip().lower()
    if s in OUR:
        return s
    for name in sorted(OUR_BY_NAME, key=len, reverse=True):  # „bardzo mało wody” przed „mało wody”
        if s.startswith(name):
            return OUR_BY_NAME[name]
    return None


def compare(our_status: str | None, cdi: Cdi) -> tuple[str, bool | None]:
    """Zdanie dla rolnika i zgodność (None – bez naszej oceny)."""
    head = f"Europejskie Obserwatorium Suszy dla tej okolicy: {cdi.label_pl} ({cdi.decade_label})"
    lvl = our_level(our_status)
    if lvl is None:
        return head + ".", None
    name, ours_dry = OUR[lvl]
    edo_dry = cdi.class_ in EDO_DRY
    if ours_dry == edo_dry:
        return f"{head} – zgodne z naszą oceną „{name}”.", True
    if ours_dry:  # my: mało wody, EDO: brak / obserwacja / regeneracja
        return (f"{head} – nasza ocena „{name}” dotyczy tej jednej działki (jej gleby i uprawy), a wskaźnik EDO "
                "opisuje całą okolicę."), False
    return (f"{head} – nasza ocena „{name}” dotyczy tej jednej działki; wskaźnik regionalny pokazuje trudniejszą "
            "sytuację w okolicy."), False


async def _decade(lon: float, lat: float, start: date, today: date) -> tuple | None:
    """Piksele czterech warstw dla dekady; None – usługa nie ma danych CDI dla tej dekady."""
    cd, rc, sm, rk = await asyncio.gather(*(edo.pixel(layer, lon, lat, start, today)
                                            for layer in ("cdiad", "cdirc", "smian", "rdria")))
    if cd[3] == 0 and rc[3] == 0:
        return None
    return cd, rc, sm, rk


def build(start: date, cd, rc, sm, rk, analysis_date: date, our_status: str | None = None) -> DroughtContext:
    cdi_class = (edo.nearest(cd[:3], edo.CDI) if cd[3] else None) or \
                (edo.nearest(rc[:3], edo.CDI_RECOVERY) if rc[3] else None) or "brak"
    cdi = Cdi(**{"class": cdi_class}, label_pl=CDI_LABEL[cdi_class], date=start, decade_label=decade_label(start))
    sma = None
    if sm[3] and edo.nearest(sm[:3], {edo.SMA_NO_DATA: 1}) is None:
        hit = edo.nearest(sm[:3], edo.SMA)
        if hit is not None:
            sma = SoilMoistureAnomaly(value=hit[0], **{"class": hit[1]}, label_pl=SMA_LABEL[hit[1]], date=start)
    if sma is None:
        sma = SoilMoistureAnomaly(value=None, label_pl="brak danych", date=start)
    risk_class = (edo.nearest(rk[:3], edo.AGRI_RISK) if rk[3] else None) or "brak"
    risk = AgriRisk(**{"class": risk_class}, label_pl=RISK_LABEL[risk_class], date=start)
    sentence, agrees = compare(our_status, cdi)
    return DroughtContext(cdi=cdi, soil_moisture_anomaly=sma, agri_risk=risk, sentence=sentence, agrees=agrees,
                          fetched_at=datetime.now(timezone.utc).replace(microsecond=0), analysis_date=analysis_date)


async def context(lon: float, lat: float, analysis_date: date, our_status: str | None = None,
                  today: date | None = None) -> DroughtContext:
    """Tło suszowe dla punktu (środek działki). Błąd / brak odpowiedzi w 8 s → `unavailable` z notą."""
    today = today or date.today()

    async def run() -> DroughtContext:
        starts = [last_complete_decade(analysis_date)]
        while len(starts) < MAX_BACK + 1:
            starts.append(previous_decade(starts[-1]))
        for i in range(0, len(starts), 2):  # po dwie dekady naraz, od najnowszych
            pair = starts[i:i + 2]
            got = await asyncio.gather(*(_decade(lon, lat, s, today) for s in pair))
            for start, px in zip(pair, got):
                if px is not None:
                    return build(start, *px, analysis_date, our_status)
        return DroughtContext(unavailable=True, analysis_date=analysis_date, note_pl=NO_DATA_NOTE)

    try:
        return await asyncio.wait_for(run(), TOTAL_TIMEOUT_S)
    except SourceError as exc:
        log_source_error("tło suszowe", exc, "EDO")
    except asyncio.TimeoutError:
        log_source_error("tło suszowe", SourceError(edo.SOURCE, f"brak odpowiedzi w {TOTAL_TIMEOUT_S:.0f} s"), "EDO")
    return DroughtContext(unavailable=True, note_pl=UNAVAILABLE_NOTE, analysis_date=analysis_date)
