"""Etykieta gleby dla rolnika (A5b-2b, D66): lekka / średnia / ciężka / organiczna – ważona udziałem.

Źródło składu (od najdokładniejszego): punkty mapy glebowo-rolniczej (gatunek w każdym z 9 punktów działki) → udziały
kategorii IUNG w działce → klasa uziarnienia SoilGrids. Kategorie agronomiczne (PTG 1989, jak w D49): I–II gleby lekkie
(piaski), III średnie (gliny lekkie, pyły), IV ciężkie (gliny średnie i ciężkie, iły).
Etykieta = średnia kategoria ważona udziałem: < 2,5 lekka, < 3,5 średnia, inaczej ciężka (D66). Przykład 201305:
7 z 9 punktów glina lekka pylasta (III), 2 z 9 piasek gliniasty lekki (II) → średnia 2,78 → „gleba średnia”,
nie „zwięzła” (błąd A6: kat. III i IV wrzucone do jednej grupy).
Dwie gleby = mniejszy składnik > 20% działki.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.soil import SoilAssessment
from app.analysis.soil_consistency import USDA_CATEGORY, MapSummary
from app.schemas.analysis import SoilTexture
from app.sources.soil_map import label as species_name

GROUP_LABEL = {"lekka": "gleba lekka", "srednia": "gleba średnia", "ciezka": "gleba ciężka",
               "organiczna": "gleba organiczna", "nieznana": "gleba nieznana"}
CATEGORY_NAME = {1: "piasek luźny lub słabogliniasty", 2: "piasek gliniasty", 3: "glina lekka lub pył",
                 4: "glina ciężka lub ił"}
TWO_SOILS_MIN_SHARE = 0.20
LIGHT_MAX_MEAN = 2.5
MEDIUM_MAX_MEAN = 3.5


@dataclass
class Part:
    share: float  # 0–1
    name: str
    category: int


@dataclass
class SoilProfile:
    group: str
    mean_category: float | None
    parts: list[Part] = field(default_factory=list)
    source: str = ""

    @property
    def label(self) -> str:
        return GROUP_LABEL[self.group]

    @property
    def two_soils(self) -> bool:
        return len(self.parts) >= 2 and self.parts[1].share > TWO_SOILS_MIN_SHARE

    def describe(self) -> str:
        """'glina lekka pylasta 78%, piasek gliniasty lekki 22%' (części ≥ 5%)."""
        parts = [p for p in self.parts if p.share >= 0.05]
        if len(parts) == 1:
            return parts[0].name
        return ", ".join(f"{p.name} {round(100 * p.share)}%" for p in parts)

    @property
    def text(self) -> str:
        return f"{self.label}: {self.describe()}" if self.parts else self.label


def group_for(mean: float | None) -> str:
    if mean is None:
        return "nieznana"
    if mean < LIGHT_MAX_MEAN:
        return "lekka"
    return "srednia" if mean < MEDIUM_MAX_MEAN else "ciezka"


def _merge(parts: list[Part]) -> list[Part]:
    by: dict[str, Part] = {}
    for p in parts:
        if p.name in by:
            by[p.name].share += p.share
        else:
            by[p.name] = Part(p.share, p.name, p.category)
    return sorted(by.values(), key=lambda p: -p.share)


def profile(soil: SoilAssessment, map_sum: MapSummary | None, texture: SoilTexture | None) -> SoilProfile:
    shares = {s.code: s.share for s in soil.shares}
    if shares.get(5, 0) > 0.5:
        return SoilProfile("organiczna", None, [Part(shares[5], "gleba organiczna (torf, mursz)", 0)], "IUNG-PIB")
    if map_sum and map_sum.counts:
        n = sum(map_sum.counts.values())
        parts = []
        for cat, k in map_sum.counts.items():
            r = map_sum.by_category[cat]
            parts.append(Part(k / n, species_name(r.species_code) or CATEGORY_NAME[cat], cat))
        parts = _merge(parts)
        src = "mapa glebowo-rolnicza"
    else:
        mineral = {c: s for c, s in shares.items() if c in (1, 2, 3, 4)}
        total = sum(mineral.values())
        if total > 0:
            parts = _merge([Part(s / total, CATEGORY_NAME[c], c) for c, s in mineral.items()])
            src = "IUNG-PIB"
        elif texture is not None and texture.texture_code in USDA_CATEGORY:
            parts = [Part(1.0, texture.texture_class, USDA_CATEGORY[texture.texture_code])]
            src = "SoilGrids"
        else:
            return SoilProfile("nieznana", None)
    mean = sum(p.share * p.category for p in parts)
    return SoilProfile(group_for(mean), round(mean, 2), parts, src)
