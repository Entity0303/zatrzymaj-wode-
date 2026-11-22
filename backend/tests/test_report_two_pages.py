"""Raport skrócony zawsze mieści się na 2 stronach: przy nadmiarze tekstu kolejne stopnie skracają listy (nie czcionkę)."""
import io

from pypdf import PdfReader

from app.report.builder import COMPACT, short_pdf


def test_short_pdf_escalates_until_two_pages():
    levels = []

    def render(level: int) -> str:
        levels.append(level)
        pages = 4 if level < 2 else 2  # dwa pierwsze układy za długie
        return "".join('<p style="break-after: page">strona</p>' for _ in range(pages - 1)) + "<p>koniec</p>"

    pdf = short_pdf(render)
    assert levels == [0, 1, 2]
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2


def test_compact_levels_only_shorten():
    for prev, nxt in zip(COMPACT, COMPACT[1:]):
        assert all(nxt[k] <= prev[k] for k in prev)
    assert COMPACT[0] == {"pt_clip": 150, "pt_n": 4, "avoid_crops": 3, "avoid_groups": 2, "act_clip": 125, "act_n": 3, "rank_n": 5}
