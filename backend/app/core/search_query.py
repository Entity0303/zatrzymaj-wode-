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
# A9: „Kraków, ul. Długa 5”, „Kraków, Długa 5a”, „Wola, al. Polna 12/3”
_STREET = re.compile(r"^(?P<loc>[^,\d]*[^\W\d_][^,]*),\s*(?:(?:ul|ulica|al|aleja|aleje|os|osiedle|pl|plac)\.?\s+)?"
                     r"(?P<street>[^\W\d_][^,]*?)\s+(?:nr\.?\s*)?(?P<num>\d{1,4}[A-Za-z]?(?:\s*/\s*\d{1,4}[A-Za-z]?)?)$",
                     re.IGNORECASE)
# A19: „Wnory-Wandy 6/1 Kobylin-Borzymy” / „Wnory-Wandy 6/1, gm. Kobylin-Borzymy” – obręb, numer, potem gmina
_NAME_NUM_TAIL = re.compile(rf"^(?P<name>[^\W\d_][^,\d]*?)[\s,;]+(?:(?:nr|dz|dz\.|działka|dzialka)\.?\s*)?(?P<num>{_NUM})"
                            r"[\s,;]+(?P<tail>[^\W\d_][^\d]*)$", re.IGNORECASE)
_ADMIN_PREFIX = re.compile(r"^(?:gm|gmina|pow|powiat|woj|województwo|wojewodztwo)\.?\s+", re.IGNORECASE)
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
    street: str | None = None  # A9: „Kraków, ul. Długa 5” → name = Kraków, street = Długa, number = 5 (tylko adres)
    # A19: „Kobylin-Borzymy, Wnory-Wandy 6/1” wygląda jak adres bez „ul.” – to może być też gmina + obręb + numer:
    # (obręb, [gmina]) do sprawdzenia w ULDK obok adresu
    alt_parcel: tuple[str, list[str]] | None = None


def admin_name(text: str) -> str:
    """„gm. Kobylin-Borzymy” / „gmina Wronki” → nazwa bez skrótu jednostki."""
    return _ADMIN_PREFIX.sub("", clean(text)).strip(" ,.")


def _norm_number(num: str) -> str:
    return re.sub(r"\s*/\s*", "/", num.strip()).replace(" ", "")


def parse(q: str | None) -> ParsedQuery:
    text = clean(q or "")
    if not text:
        return ParsedQuery("empty", "")
    if _FULL_ID.match(text.replace(" ", "")):
        pid = text.replace(" ", "")
        return ParsedQuery("parcel_id", pid, parcel_id=pid)
    ms = _STREET.match(text)
    if ms and not re.fullmatch(r"(?:gm|gmina|pow|powiat|woj)\.?\s.*", ms.group("street"), re.IGNORECASE):
        loc, street = clean(ms.group("loc")).strip(" ,."), clean(ms.group("street")).strip(" ,.")
        prefixed = re.search(r",\s*(?:ul|ulica|al|aleja|aleje|os|osiedle|pl|plac)\.?\s", text, re.IGNORECASE)
        return ParsedQuery("obreb_numer", text, name=loc, number=_norm_number(ms.group("num")), street=street,
                           alt_parcel=None if prefixed else (street, [admin_name(loc)]))
    m = _NUM_THEN_NAME.match(text) or _NAME_THEN_NUM.match(text)
    if m:
        name = clean(m.group("name")).strip(" ,.")
        if name and "," in name:  # A19: „gm. Kobylin-Borzymy, Wnory-Wandy 6/1” – ostatnia część = obręb, reszta = filtr
            parts = [admin_name(x) for x in name.split(",") if admin_name(x)]
            if parts:
                return ParsedQuery("obreb_numer", text, name=parts[-1], number=_norm_number(m.group("num")),
                                   area_hint=parts[:-1])
        if name:
            return ParsedQuery("obreb_numer", text, name=name, number=_norm_number(m.group("num")))
    mt = _NAME_NUM_TAIL.match(text)
    if mt:
        name, tail = clean(mt.group("name")).strip(" ,."), admin_name(mt.group("tail"))
        if name and tail:
            return ParsedQuery("obreb_numer", text, name=name, number=_norm_number(mt.group("num")), area_hint=[tail])
    if re.fullmatch(r"[\d\s/\-_.]+", text):  # same cyfry – bez nazwy nie wiadomo, o którą wieś chodzi
        return ParsedQuery("unrecognized", text)
    head, *tail = [p.strip() for p in text.split(",")]
    if head and _ONLY_NAME.match(head):
        return ParsedQuery("name", text, name=head, area_hint=[t for t in tail if t])
    return ParsedQuery("unrecognized", text)
