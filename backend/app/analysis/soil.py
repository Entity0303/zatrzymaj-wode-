"""Gleba działki: kategorie podatności na suszę IUNG -> „ile wody zmieści gleba” (WOD), klasy EGiB.

Wejście: wynik sources/iung.py (albo SourceError) i sources/kieg.py (albo SourceError / None).
Wyjście: `SoilAssessment` – wskaźnik `indicators.soil_capacity` z kontraktu, wpisy do
`reliability.sources` i `reliability.limitations`, plus dane, których kontrakt jeszcze nie ma
(udziały kategorii, klasy bonitacyjne, flaga „to nie jest grunt rolny”) – patrz .ai/status.

Zasady: błąd IUNG nie wywraca analizy – WOD = brak danych, pewność obniżona. Klasy EGiB
tylko informacyjnie (D4) – ich brak nie obniża pewności.
"""

from dataclasses import dataclass, field

from app.schemas.analysis import Indicator, SourceStatus, SourceTag, StatusLevel
from app.core.http import SourceError
from app.sources import iung, kieg
from app.sources.iung import CODES, MINERAL, SoilResult

# Kategoria podatności -> status karty (kategoria I = najmniej wody w glebie)
CATEGORY_STATUS: dict[int, StatusLevel] = {1: "risk", 2: "warn", 3: "ok", 4: "ok"}
CATEGORY_SHORT = {1: "Kat. I – bardzo podatna na suszę", 2: "Kat. II – podatna na suszę",
                  3: "Kat. III – średnio podatna na suszę", 4: "Kat. IV – mało podatna na suszę"}
NON_AGRI_TEXT = {
    5: "gleby organiczne (torfy, mursze) – kategorie podatności IUNG ich nie obejmują",
    11: "las lub zadrzewienie",
    12: "woda",
    13: "teren zabudowany",
    14: "droga lub nieużytek",
}


@dataclass
class SoilShare:
    code: int
    label: str
    share: float


@dataclass
class SoilAssessment:
    soil_capacity: Indicator  # kontrakt: indicators.soil_capacity
    dominant_code: int | None = None
    dominant_label: str | None = None
    shares: list[SoilShare] = field(default_factory=list)
    agricultural_share: float | None = None
    wod_mm: float | None = None
    method: str | None = None  # "wcs" | "punkty"
    cells: int | None = None
    classes: list[str] | None = None  # EGiB, informacyjnie
    land_use: list[str] | None = None
    not_agricultural: bool = False
    not_agricultural_reason: str | None = None
    sources: list[SourceStatus] = field(default_factory=list)  # kontrakt: reliability.sources
    limitations: list[str] = field(default_factory=list)  # kontrakt: reliability.limitations
    degrades_confidence: bool = False


def _iung_failed(err: SourceError) -> SoilAssessment:
    return SoilAssessment(
        soil_capacity=Indicator(
            value=None,
            unit="mm",
            label=None,
            status="no_data",
            note="Nie udało się pobrać mapy gleb IUNG",
            source_tag=SourceTag(kind="brak_danych", source=iung.SOURCE_SHORT),
        ),
        sources=[
            SourceStatus(name=iung.SOURCE_SHORT, used_for="kategoria gleby, ile wody zmieści gleba",
                         data_date=None, resolution=iung.RESOLUTION, status="brak", note=err.message)
        ],
        limitations=["Brak danych o glebie (IUNG nie odpowiada) – nie wiadomo, ile wody zmieści gleba; pewność wyniku obniżona."],
        degrades_confidence=True,
    )


def assess_soil(iung_res: SoilResult | SourceError, kieg_res: "kieg.KiegResult | SourceError | None" = None) -> SoilAssessment:
    if isinstance(iung_res, SourceError):
        out = _iung_failed(iung_res)
    else:
        out = _from_iung(iung_res)
    _add_kieg(out, kieg_res)
    return out


def _from_iung(r: SoilResult) -> SoilAssessment:
    shares = [SoilShare(c, CODES.get(c, ("Nieznany kod",))[0], s) for c, s in r.shares.items()]
    limitations: list[str] = []
    non_agri = r.not_agricultural_code
    wod = r.wod_mm
    dom_min = r.dominant_mineral

    if non_agri is not None:
        reason = NON_AGRI_TEXT.get(non_agri, CODES[non_agri][0].lower())
        indicator = Indicator(
            value=None,
            unit="mm",
            label="Nie dotyczy",
            status="no_data",
            note=f"Według mapy gleb IUNG większość działki to {reason} – ocena suszy rolniczej nie ma tu zastosowania.",
            source_tag=SourceTag(kind="pomiar", source=iung.SOURCE_SHORT),
        )
    elif wod is None:
        indicator = Indicator(
            value=None, unit="mm", label=None, status="no_data",
            note="Brak gleb mineralnych użytków rolnych w obrysie działki",
            source_tag=SourceTag(kind="brak_danych", source=iung.SOURCE_SHORT),
        )
    else:
        indicator = Indicator(
            value=round(wod),
            unit="mm",
            label=CATEGORY_SHORT[dom_min] if dom_min else None,
            status=CATEGORY_STATUS.get(dom_min, "no_data") if dom_min else "no_data",
            note=f"woda dostępna dla roślin (WOD) – {round(r.agricultural_share * 100)}% działki to gleby mineralne użytków rolnych",
            source_tag=SourceTag(kind="pomiar", source=iung.SOURCE_SHORT),
        )

    if any(s.code not in MINERAL for s in shares):
        limitations.append(
            "Kategorie podatności IUNG obejmują tylko gleby mineralne użytków rolnych – lasy, wody, zabudowa, "
            "drogi i gleby organiczne nie mają kategorii (pominięte w WOD)."
        )
    if r.nodata_share > 0:
        limitations.append(f"{round(r.nodata_share * 100)}% działki poza zasięgiem mapy gleb IUNG.")
    if r.method == "punkty":
        limitations.append(
            f"Mapa gleb sprawdzona metodą zapasową w {r.total + r.nodata} punktach – udziały kategorii przybliżone."
        )
    if wod is not None and non_agri is None:
        limitations.append(
            "WOD to wartość typowa dla kategorii gleby (środek przedziału IUNG), nie pomiar na tej działce."
        )

    dom = r.dominant
    return SoilAssessment(
        soil_capacity=indicator,
        dominant_code=dom,
        dominant_label=CODES.get(dom, ("Nieznany kod",))[0] if dom is not None else None,
        shares=shares,
        agricultural_share=r.agricultural_share,
        wod_mm=wod,
        method=r.method,
        cells=r.total + r.nodata,
        not_agricultural=non_agri is not None,
        not_agricultural_reason=NON_AGRI_TEXT.get(non_agri) if non_agri is not None else None,
        sources=[
            SourceStatus(
                name=iung.SOURCE_SHORT,
                used_for="kategoria gleby, ile wody zmieści gleba",
                data_date=None,
                resolution=iung.RESOLUTION if r.method == "wcs" else f"{r.total + r.nodata} punktów",
                status="ok" if r.method == "wcs" and r.nodata_share < 0.5 else "czesciowo",
                note=None if r.method == "wcs" else "metoda zapasowa (punkty)",
            )
        ],
        limitations=limitations,
        degrades_confidence=r.method != "wcs" or r.nodata_share >= 0.5,
    )


def _add_kieg(out: SoilAssessment, k: "kieg.KiegResult | SourceError | None") -> None:
    if k is None:
        return
    if isinstance(k, SourceError):
        out.sources.append(SourceStatus(name="EGiB (KIEG)", used_for="klasy bonitacyjne (informacyjnie)",
                                        data_date=None, status="brak", note=k.message))
        out.limitations.append("Klasy bonitacyjne niedostępne (usługa KIEG nie odpowiada) – to tylko informacja dodatkowa.")
        return
    out.classes, out.land_use = k.classes, k.land_use
    out.sources.append(SourceStatus(
        name="EGiB (KIEG)", used_for="klasy bonitacyjne (informacyjnie)", data_date=k.published,
        status="ok" if k.available else "brak", note=k.note))
    if k.available:
        cls = ", ".join(k.classes or [])
        out.soil_capacity.note = (out.soil_capacity.note + "; " if out.soil_capacity.note else "") + f"klasy bonitacyjne EGiB: {cls}"
    else:
        out.limitations.append("Klasy bonitacyjne niedostępne w tym powiecie (EGiB) – to tylko informacja dodatkowa.")
