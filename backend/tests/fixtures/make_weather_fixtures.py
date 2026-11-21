"""Generuje syntetyczne odpowiedzi NASA POWER i archiwum Open-Meteo do testów (deterministycznie).

Uruchom: python tests/fixtures/make_weather_fixtures.py   (z katalogu backend/)
Dane NIE są prawdziwe – tylko kształt odpowiedzi API + celowe braki:
- NASA: 2017-05-10 brak RH2M (→ Hargreaves), 2018-04-02 brak opadu, 2018-07-12..14 wszystko -999
  (opóźnienie źródła),
- Open-Meteo: 2018-07-13..14 null (opóźnienie archiwum).
"""

import json
import math
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
START, END = date(2017, 1, 1), date(2018, 7, 14)


def days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


def weather(d: date) -> dict:
    doy = d.timetuple().tm_yday
    season = math.sin(2 * math.pi * (doy - 105) / 365)  # max w lipcu
    tmax = round(13 + 13 * season + 2 * math.sin(doy / 3), 2)
    tmin = round(tmax - 9 - 2 * math.cos(doy / 5), 2)
    # deszcz co 4. dzień; 2018 suchszy (opad × 0,5)
    rain = (6.0 + 3 * math.sin(doy)) if doy % 4 == 0 else 0.2
    if d.year == 2018:
        rain *= 0.5
    return {
        "PRECTOTCORR": round(rain, 2),
        "T2M_MAX": tmax,
        "T2M_MIN": tmin,
        "RH2M": round(75 - 10 * season, 2),
        "WS2M": round(2.5 + 0.8 * math.cos(doy / 7), 2),
        "ALLSKY_SFC_SW_DWN": round(max(1.0, 14 + 12 * season), 2),
    }


def nasa() -> dict:
    params = {k: {} for k in ("PRECTOTCORR", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN")}
    for d in days():
        v = weather(d)
        if d == date(2017, 5, 10):
            v["RH2M"] = -999.0
        if d == date(2018, 4, 2):
            v["PRECTOTCORR"] = -999.0
        if d >= date(2018, 7, 12):
            v = {k: -999.0 for k in v}
        for k, x in v.items():
            params[k][d.strftime("%Y%m%d")] = x
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [22.6, 52.9, 132.5]},
        "properties": {"parameter": params},
        "header": {"title": "SYNTETYCZNE dane testowe w formacie NASA/POWER", "fill_value": -999.0},
    }


def open_meteo() -> dict:
    t, p, e, tx, tn = [], [], [], [], []
    for d in days():
        v = weather(d)
        lagged = d >= date(2018, 7, 13)
        t.append(d.isoformat())
        p.append(None if lagged else v["PRECTOTCORR"])
        e.append(None if lagged else round(1.0 + 3.0 * max(0.0, math.sin(2 * math.pi * (d.timetuple().tm_yday - 80) / 365)), 2))
        tx.append(None if lagged else v["T2M_MAX"])
        tn.append(None if lagged else v["T2M_MIN"])
    return {
        "latitude": 52.9,
        "longitude": 22.6,
        "elevation": 131.0,
        "timezone": "Europe/Warsaw",
        "daily_units": {"time": "iso8601", "precipitation_sum": "mm", "et0_fao_evapotranspiration": "mm"},
        "daily": {
            "time": t,
            "precipitation_sum": p,
            "et0_fao_evapotranspiration": e,
            "temperature_2m_max": tx,
            "temperature_2m_min": tn,
        },
    }


if __name__ == "__main__":
    (HERE / "nasa_power_2017_2018.json").write_text(json.dumps(nasa(), separators=(",", ":")), encoding="utf-8")
    (HERE / "open_meteo_archive_2017_2018.json").write_text(
        json.dumps(open_meteo(), separators=(",", ":")), encoding="utf-8"
    )
    print("ok")
