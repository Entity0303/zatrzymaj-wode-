"""A23 – wspólny ogranicznik zadań w tle: limit BACKGROUND_WORKERS, kolejność teren → widełki → rowy → satelita →
SoilGrids, zwolnienie miejsca po błędzie, log start / koniec / błąd."""

import asyncio
import logging

import pytest

from app.core import background
from app.core.config import settings


def test_limit_and_start_order(monkeypatch):
    monkeypatch.setattr(settings, "background_workers", 2)
    monkeypatch.setattr(background, "GRACE_S", {"satelita": 0.001, "soilgrids": 0.002})
    starts, running, peak = [], [0], [0]

    async def job(name, delay):
        starts.append(name)
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        await asyncio.sleep(delay)
        running[0] -= 1
        return name

    async def main():
        first = [asyncio.ensure_future(background.run("teren", "a", job("a", 0.05))),
                 asyncio.ensure_future(background.run("teren", "b", job("b", 0.05)))]
        await asyncio.sleep(0.01)
        assert background.busy()  # oba miejsca zajęte – nowe zadania czekają
        later = [asyncio.ensure_future(background.run(kind, name, job(name, 0.01)))
                 for kind, name in (("soilgrids", "c"), ("satelita", "d"), ("rowy", "e"), ("widelki", "f"), ("teren", "g"))]
        out = await asyncio.gather(*first, *later)
        assert not background.busy()
        return out

    assert asyncio.run(main()) == ["a", "b", "c", "d", "e", "f", "g"]
    assert starts[:2] == ["a", "b"] and starts[2:] == ["g", "f", "e", "d", "c"]  # teren → widełki → rowy → satelita → SoilGrids
    assert peak[0] == 2
    assert settings.model_fields["background_workers"].default == 2


def test_error_releases_slot_and_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(settings, "background_workers", 1)

    async def boom():
        raise ValueError("zepsute")

    async def ok():
        return 7

    async def main():
        with pytest.raises(ValueError):
            await background.run("teren", "dzialka-1", boom())
        return await background.run("teren", "dzialka-2", ok())  # miejsce zwolnione mimo błędu

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert asyncio.run(main()) == 7
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("TŁO")]
    assert any(m.startswith("TŁO start teren dzialka-1") for m in lines)
    assert any(m.startswith("TŁO błąd teren dzialka-1") and "ValueError" in m for m in lines)
    assert any(m.startswith("TŁO koniec teren dzialka-2 w ") for m in lines)


def test_queued_soilgrids_does_not_block_analysis(monkeypatch):
    """Wszystkie miejsca zajęte → SoilGrids od razu „w toku” (bez czekania 5 s), pobranie rusza po zwolnieniu miejsca."""
    from app.core.http import SourceError
    from app.sources import soilgrids

    monkeypatch.setattr(settings, "background_workers", 1)
    monkeypatch.setattr(background, "GRACE_S", {"soilgrids": 0.001})
    done = []

    async def fake_texture(lon, lat):
        done.append((lon, lat))
        return "wynik"

    monkeypatch.setattr(soilgrids, "texture_at", fake_texture)

    async def main():
        blocker = asyncio.ensure_future(background.run("teren", "x", asyncio.sleep(0.1)))
        await asyncio.sleep(0.01)
        t0 = asyncio.get_running_loop().time()
        with pytest.raises(SourceError) as e:
            await soilgrids.texture_budget(21.0, 52.0, wait_s=5.0)
        waited = asyncio.get_running_loop().time() - t0
        await blocker
        await asyncio.sleep(0.05)
        return e.value.message, waited

    msg, waited = asyncio.run(main())
    assert msg == soilgrids.PENDING_MESSAGE and waited < 0.05 and done == [(21.0, 52.0)]


def test_low_priority_yields_to_terrain_submitted_just_after(monkeypatch):
    """Satelita i SoilGrids są zgłaszane ułamek sekundy przed terenem – zwłoka startu daje pierwszeństwo terenowi."""
    monkeypatch.setattr(settings, "background_workers", 1)
    monkeypatch.setattr(background, "GRACE_S", {"satelita": 0.02, "soilgrids": 0.04})
    starts = []

    async def job(name):
        starts.append(name)
        await asyncio.sleep(0.03)

    async def main():
        tasks = [asyncio.ensure_future(background.run("satelita", "s", job("satelita"))),
                 asyncio.ensure_future(background.run("soilgrids", "g", job("soilgrids")))]
        await asyncio.sleep(0.005)
        tasks.append(asyncio.ensure_future(background.run("teren", "t", job("teren"))))
        assert background.busy("soilgrids") and background.busy("satelita")  # analiza na nie nie czeka
        await asyncio.gather(*tasks)

    asyncio.run(main())
    assert starts == ["teren", "satelita", "soilgrids"]
