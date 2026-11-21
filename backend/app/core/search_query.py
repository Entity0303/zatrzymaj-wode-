"""Rozpoznawanie, czego szuka rolnik (A5c): identyfikator działki, „obręb + numer” albo sama nazwa miejscowości.

Czyste funkcje, bez sieci. Normalizacja nazw (`fold`) – małe litery, bez polskich znaków, myślnik = spacja – służy do
porównań i do wzorców geokodera; do usługi wysyłamy nazwy z polskimi znakami (kanoniczne z PRNG / słownika).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

QueryKind = Literal["parcel_id", "obreb_numer", "name", "empty", "unrecognized"]

_FULL_ID = re.compile(r"^\d{6}_\d\.\d{4}\.\S+$")
# numer działki: 123, 123/4, 12a, 12A/3, „6 / 1”
_NUM = r"\d{1,5}[A-Za-z]?(?:\s*/\s*\d{1,5}[A-Za-z]?)?"
_NAME_THEN_NUM = re.compile(rf"^(?P<name>.*?[^\W\d_])[\s,;]+(?:(?:nr|dz|dz\.|działka|dzialka)\.?\s*)?(?P<num>{_NUM})$",
                            re.IGNORECASE)
_NUM_THEN_NAME = re.compile(rf"^(?:(?:nr|dz|działka|dzialka)\.?\s*)(?P<num>{_NUM})[\s,;]+(?P<name>[^\W\d_].*)$",
                            re.IGNORECASE)
_ONLY_NAME = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ \-.'’()])*$")
_LETTERS = str.maketrans({"ł": "l", "Ł": "L", "đ": "d", "ø": "o"})
HINT = "Wpisz nazwę wsi albo obręb i numer działki, np. Wnory-Wandy 6/1"


def fold(text: str) -> str:
    """'Wnory–Wandy' / 'WNORY  wandy' / 'Tczów' → 'wnory wandy' / 'tczow' (porównania bez polskich znaków)."""
    t = unicodedata.normalize("NFKD", text.translate(_LETTERS))
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    t = re.sub(r"[\s\-–—_.,;()]+", " ", t)
    return t.strip()


def clean(text: str) -> str:
    """Spacje i separatory zwinięte do jednej spacji; myślniki typograficzne → '-'."""
    t = text.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"[\s;]+", " ", t).strip()


@dataclass
class ParsedQuery:
    kind: QueryKind
    text: str                 # oczyszczone zapytanie
    name: str | None = None   # nazwa (obręb / miejscowość)
    number: str | None = None  # numer działki, np. 6/1
    parcel_id: str | None = None
    area_hint: list[str] = field(default_factory=list)  # po przecinku: gmina / powiat / województwo, np. „Nowa Wieś, Busko”


def _norm_number(num: str) -> str:
    return re.sub(r"\s*/\s*", "/", num.strip()).replace(" ", "")


def parse(q: str | None) -> ParsedQuery:
    text = clean(q or "")
    if not text:
        return ParsedQuery("empty", "")
    if _FULL_ID.match(text.replace(" ", "")):
        pid = text.replace(" ", "")
        return ParsedQuery("parcel_id", pid, parcel_id=pid)
    m = _NUM_THEN_NAME.match(text) or _NAME_THEN_NUM.match(text)
    if m:
        name = clean(m.group("name")).strip(" ,.")
        if name:
            return ParsedQuery("obreb_numer", text, name=name, number=_norm_number(m.group("num")))
    if re.fullmatch(r"[\d\s/\-_.]+", text):  # same cyfry – bez nazwy nie wiadomo, o którą wieś chodzi
        return ParsedQuery("unrecognized", text)
    head, *tail = [p.strip() for p in text.split(",")]
    if head and _ONLY_NAME.match(head):
        return ParsedQuery("name", text, name=head, area_hint=[t for t in tail if t])
    return ParsedQuery("unrecognized", text)
