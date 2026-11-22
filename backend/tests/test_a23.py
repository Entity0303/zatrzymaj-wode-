"""A23 – plony z lat własnego województwa (nawet 1–2 lata), komplet punktów mapy glebowo-rolniczej, nagłówek werdyktu
zgodny z rankingiem, klient HTTP po IPv4."""

import asyncio

import pytest
from shapely.geometry import box

from app.analysis import suggestions as S
from app.analysis import verdict as V
from app.core.config import settings
from app.core.http import SourceError
from app.sources import soil_map


def test_potential_uses_own_voivodeship_even_with_two_years():
    pot = S.potential("pszenica_ozima", "podlaskie", before_year=2018, target_year=2018)  # GUS: 2016–2017
    assert pot.scope == "wojewodztwo" and pot.years == 2 and (pot.first_year, pot.last_year) == (2016, 2017)
    assert pot.ym_t_ha < 3.6  # 3,21 i 3,44 t/ha – nie P90 wszystkich województw (ok. 5,8)
    one = S.potential("pszenica_ozima", "podlaskie", before_year=2017)
    assert one.scope == "wojewodztwo" and one.years == 1
    assert S.potential("pszenica_ozima", "nieznane").scope == "kraj"  # brak lat województwa → wszystkie województwa
    assert S.potential("pszenica_ozima", "podlaskie", before_year=2016).scope == "brak"
    assert S.BUILD_MEMO_MAX == 256


def _headline(lv, n_bad):
    return next(h["text"] for h in V.cfg()["headlines"] if V._match(h["if"], lv, 0.0, 0.0, n_bad))


def test_headline_does_not_contradict_ranking():
    light_dry = {"gleba": "bad", "opady": "bad", "teren": "warn", "uprawy": "warn"}
    assert _headline(light_dry, 3).startswith("Słaba, sucha działka")          # ranking coś odradza
    assert _headline(light_dry, 0) == "Lekka ziemia – uważaj w suche lata"     # 040106: nic nie odradza, pszenica polecana
    assert _headline({**light_dry, "opady": "ok"}, 0) == "Lekka ziemia – uważaj w suche lata"
    medium = {"gleba": "warn", "opady": "bad", "teren": "ok", "uprawy": "warn"}
    assert _headline(medium, 2).startswith("Trudna działka")
    assert not _headline(medium, 0).startswith("Trudna")  # bez odradzanych upraw nie „mało wody dla wymagających upraw”


def test_soil_map_retries_failed_points_and_reports_incomplete(monkeypatch):
    calls: dict[tuple, int] = {}
    order: list[tuple] = []
    res = soil_map.SoilMapResult("4", "pgm", (), 1970)

    async def flaky(lon, lat):
        k = (round(lon, 5), round(lat, 5))
        if k not in order:
            order.append(k)
        calls[k] = calls.get(k, 0) + 1
        idx = order.index(k)
        if idx == 2 and calls[k] == 1:  # trzeci punkt: pierwszy raz błąd, przy ponowieniu OK
            raise SourceError(soil_map.SOURCE, "brak odpowiedzi w 8 s")
        if idx == 4:                     # piąty punkt: zawsze błąd
            raise SourceError(soil_map.SOURCE, "brak odpowiedzi w 8 s")
        return res

    monkeypatch.setattr(soil_map, "soil_map_at", flaky)
    geom = box(637000, 486000, 637200, 486200)
    out = asyncio.run(soil_map.soil_map_for_parcel(geom))
    assert len(out) == soil_map.PARCEL_POINTS and out.failed == 1 and sum(r is not None for r in out) == 8
    assert max(calls.values()) == 2  # nieudane punkty ponowione dokładnie raz

    async def dead(lon, lat):
        raise SourceError(soil_map.SOURCE, "nie działa")

    monkeypatch.setattr(soil_map, "soil_map_at", dead)
    with pytest.raises(SourceError):
        asyncio.run(soil_map.soil_map_for_parcel(geom))


def test_http_client_ipv4_only():
    from app.core import http

    assert settings.http_ipv4_only is True
    asyncio.run(http.close_client())
    c = http.get_client()
    pool = c._transport._pool
    assert getattr(pool, "_local_address", None) == "0.0.0.0"
    asyncio.run(http.close_client())
