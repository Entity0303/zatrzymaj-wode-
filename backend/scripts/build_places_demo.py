"""Buduje słownik miejscowości dla działek demo (app/data/places_demo.json) z PRNG GUGiK – żeby wyszukiwanie po
nazwie działało offline (DEMO_OFFLINE) dla miejscowości z przykładów. Uruchamiać na sieci, w której PRNG odpowiada:

    docker compose exec backend python scripts/build_places_demo.py

Zapisuje prawdziwe wpisy z PRNG (nazwa, rodzaj, gmina, powiat, województwo, punkt) z datą pobrania.
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.search_query import fold  # noqa: E402
from app.sources import prng  # noqa: E402

# (nazwa, fragment gminy – tylko ta miejscowość; None = wszystkie o tej nazwie)
WANTED = [
    ("Wnory-Wandy", "Kobylin"), ("Szczytno", "Kampinos"), ("Rybczewice", "Rybczewice"), ("Lasotka", None),
    ("Szadłowice", "Gniewkowo"), ("Stęszew", "Stęszew"), ("Korfantów", "Korfantów"), ("Tczów", "Tczów"),
]
OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "places_demo.json"


async def main() -> None:
    places = []
    for name, gm in WANTED:
        rows, _ = await prng.search(name)
        rows = [r for r in rows if gm is None or fold(gm) in fold(r.gmina)]
        exact = [r for r in rows if fold(r.name) == fold(name)]
        rows = exact or rows  # brak dokładnej nazwy (np. Rybczewice Drugie / Pierwsze) – wszystkie z tą gminą
        print(f"{name}: {len(rows)} wpisów", [(r.gmina, r.powiat, r.wojewodztwo) for r in rows])
        for r in rows:
            places.append({"name": r.name, "type": "miejscowosc", "type_label": r.kind or "miejscowość", "gmina": r.gmina,
                           "powiat": r.powiat, "wojewodztwo": r.wojewodztwo, "lon": r.lon, "lat": r.lat,
                           "prng_id": r.prng_id})
    OUT.write_text(json.dumps({
        "_opis": f"Słownik miejscowości dla działek demo (A5c, D73) – zapis z PRNG GUGiK z {date.today().isoformat()}; "
                 "wyszukiwanie po nazwie działa z nim offline. Odtwarza: scripts/build_places_demo.py.",
        "places": places}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("zapisano", OUT, len(places))


asyncio.run(main())
