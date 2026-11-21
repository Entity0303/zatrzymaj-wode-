"""EGiB / KIEG GUGiK – klasy bonitacyjne gleb (CLAUDE.md, źródło 6).

https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow
GetFeatureInfo, warstwy `kontury,uzytki`, INFO_FORMAT=text/html, pole „Oznaczenie konturu”
(np. RIIIa, PsIII). Tylko część powiatów – informacja dodatkowa, NIE podstawa obliczeń.

TODO (osoba A):
- klasy bonitacyjne w kilku punktach obrysu -> udziały,
- granice sąsiednich działek do mapy (SPEC 5.1),
- brak usługi w powiecie = komunikat w „ograniczeniach”, nie błąd analizy.
"""

SOURCE = "KIEG / EGiB GUGiK"
