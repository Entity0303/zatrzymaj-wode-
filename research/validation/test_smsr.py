"""Testy offline parsera stron IUNG SMSR (na zapisanym wyniku parsowania i małej próbce HTML)."""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smsr as S  # noqa: E402

PROGI = json.loads((HERE / "data" / "smsr_progi.json").read_text(encoding="utf-8"))


def test_thresholds_known_values():
    # Rozporządzenie MRiRW 11.04.2019 – zboża ozime, kat. I: 21.III–20.V = −129 mm; kukurydza: brak w 3 pierwszych okresach
    assert PROGI["Zboża ozime"]["I"][0] == -129
    assert PROGI["Zboża ozime"]["IV"][8] == -306
    assert PROGI["Kukurydza na ziarno"]["III"][:3] == [None, None, None]
    assert PROGI["Kukurydza na ziarno"]["III"][3] == -236
    assert len(PROGI) == 14 and all(len(v) == 4 for v in PROGI.values())


SAMPLE = """<section><table>
<tr><th>Gatunek roślin uprawnych</th><th>01</th><th>02</th><th>03</th><th>04</th><th>05</th><th>06</th><th>07</th>
<th>08</th><th>09</th><th>10</th><th>11</th><th>12</th><th>13</th><th>14</th></tr></table>
<h5>Kategoria gleby I</h5><table>
<tr><td>Zboża ozime</td><td>-</td><td>-</td><td>+</td><td>+</td><td>+</td><td>+</td><td>+</td><td>-</td><td>-</td>
<td>x</td><td>x</td><td>x</td><td>x</td><td>x</td></tr></table>
<h5>Kategoria gleby II</h5><table>
<tr><td>Burak cukrowy</td><td>#</td><td>#</td><td>#</td><td>#</td><td>#</td><td>#</td><td>#</td><td>#</td><td>#</td>
<td>#</td><td>#</td><td>#</td><td>#</td><td>#</td></tr></table>
<h5>Udział powierzchni zagrożonej suszą [%]</h5></section>"""


def test_parse_gmina_sample():
    g = S.parse_gmina(SAMPLE)
    assert g["I"]["Zboża ozime"][:5] == ["-", "-", "+", "+", "+"]
    assert g["I"]["Zboża ozime"][9] == "x"
    assert g["II"]["Burak cukrowy"][0] == "#"


def test_agree_counts():
    rows = [{"zgodne_nasa": True, "iung": "+", "nasz_nasa": "+"},
            {"zgodne_nasa": False, "iung": "+", "nasz_nasa": "-"},
            {"zgodne_nasa": True, "iung": "-", "nasz_nasa": "-"},
            {"zgodne_nasa": False, "iung": "-", "nasz_nasa": "+"}]
    a = S._agree(rows, "nasa")
    assert (a["n"], a["zgodne"], a["susza_iung"], a["susza_obie"], a["susza_tylko_nasza"]) == (4, 2, 2, 1, 1)
    assert a["pct"] == pytest.approx(50.0)
