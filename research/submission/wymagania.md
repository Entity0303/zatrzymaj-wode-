# Wymagania KOWR – lista kontrolna zgłoszenia (szkic C, Dominik zatwierdza)

Źródło: `docs/kowr/KOWR - Pełna treść zadania konkursowego.pdf` (rozdz. 3–7) i `KOWR - Regulamin zadania konkursowego.pdf`. Stan repo: 2026-11-21, gałąź `c/research` po INT2.
Legenda: ✅ mamy · 🟡 częściowo · ❌ brakuje.

## A. Elementy zgłoszenia (rozdz. 4.1)
| Wymaganie | Stan | Gdzie to mamy / czego brakuje |
|---|---|---|
| Nazwa zespołu i tytuł rozwiązania | 🟡 | tytuł: „Wodoskop – prześwietl swoją działkę pod kątem suszy” (D72); **nazwa zespołu – do wpisania** |
| Zwięzły opis: problem, funkcje, użycie danych, korzyści | 🟡 | szkic `research/submission/opis.md` |
| Link do prywatnego repozytorium | ✅ | github.com/Entity0303/zatrzymaj-wode- (prywatne do końca wydarzenia; dostęp jury wg instrukcji z platformy) |
| README lub równoważna dokumentacja | ❌ | **w katalogu głównym repo nie ma README.md** – sekcja B niżej |
| Prezentacja PDF do 10 slajdów | ❌ | szkic treści `research/submission/slajdy.md`; PDF do zrobienia |
| Działający prototyp + link albo instrukcja uruchomienia w README | 🟡 | `docker compose up`, `DEMO_OFFLINE`, `warm_demo.py` (`.ai/status/a-backend.md`); instrukcja musi trafić do README |
| Film do 3 minut | ❌ | scenariusz `research/submission/film.md`; nagranie do zrobienia |
| Raport(y) wygenerowane przez prototyp | ✅ | `reports/examples/*.pdf` (dobra / słaba działka, susza 2018, mokry 2021, kukurydza, „to nie jest pole”) |

## B. README / dokumentacja techniczna (rozdz. 4.2) – wszystko ❌ dopóki nie ma README
| # | Wymagany punkt | Skąd wziąć treść |
|---|---|---|
| 1 | Instrukcja uruchomienia | `.ai/status/a-backend.md` („Przed prezentacją”), `docker-compose.yml` |
| 2 | Opis funkcji | `research/submission/opis.md` |
| 3 | Skrócony opis architektury | `CLAUDE.md` (Stack, Struktura) |
| 4 | Źródła i zakresy danych | `CLAUDE.md` (Źródła danych), `research/precip/SOURCES.md` |
| 5 | Które dane na bieżąco, a które pobrane wcześniej + daty | na bieżąco: ULDK, NASA POWER, IUNG, mapa glebowo-rolnicza, NMT, prognoza; wcześniej: plony GUS (`research/data/gus_raw/`, pobrane 2026-11-21), `crops.csv`, zapisany teren C (`backend/app/data/terrain/`), indeks stacji IMGW (`research/precip/data/`, 2026-11-21) |
| 6 | Biblioteki, komponenty, modele, usługi, **narzędzia AI** | backend `requirements.txt`, frontend `package.json`; **AI: Claude Code (asystent programowania) – do wpisania zakres użycia**; w działaniu aplikacji LLM nie liczy niczego (CLAUDE.md) |
| 7 | Licencje danych i komponentów | tylko MIT/BSD/Apache, Inter OFL (CLAUDE.md); licencje danych: GUGiK, IMGW, IUNG, GUS, NASA, Open-Meteo, SoilGrids CC BY 4.0 (D41) – **zebrać w jednej tabeli** |
| 8 | Znane ograniczenia techniczne | `research/precip/REPORT.md`, `research/terrain/NOTES.md`, D-decyzje; blokady ULDK/NMT (D45, D54) |
| 9 | Jak weryfikujemy wyniki | testy backendu (343 bez sieci), `research/` (69 testów), kalibracja GUS (D61), test słabej ziemi (D70), porównanie opadów (`research/precip/REPORT.md`) |

## C. Zakres obowiązkowy prototypu (rozdz. 3.3)
| Wymaganie | Stan | Gdzie |
|---|---|---|
| Uruchomienie w przeglądarce (Chrome, Firefox, Edge, Safari, Opera), bez instalacji | ✅ | frontend React/Vite |
| Telefon (atut) | ✅ | wersja mobilna (`design/ref-mobile.png`, B1) |
| Działka po numerze albo na mapie | ✅ | `/api/parcel`, wyszukiwarka, punkt `lon/lat` (D69) |
| Wybór uprawy | ✅ | 15 upraw IUNG + „bez uprawy” (stan działki, D50) |
| Dane bieżące i 10 lat, wynik liczony (nie gotowe teksty) | ✅ | `/api/analysis`, reguły YAML (D38) |
| Raport: niedobór i przyczyny, rekomendacje z danymi, data i źródła, ograniczenia, braki wprost | ✅ | `/api/report.pdf` (D46, D71) |
| Zapis / PDF / wydruk | ✅ | PDF, wydruk paszportu |
| Kolejność: ocena → retencja/agrotechnika → nawadnianie | ✅ | D38, D42 |
| **Dane satelitarne** (wymagana kategoria; ocena wilgotności „w szczególności wskaźniki satelitarne”) | ❌ | `backend/app/sources/sentinel.py` – tylko TODO; pewność −15 pkt za brak (D36) |
| Dane meteorologiczne | ✅ | NASA POWER, Open-Meteo; IMGW – badanie C4, wdrożenie A7 |
| Dane glebowe | ✅ | IUNG, mapa glebowo-rolnicza, SoilGrids, KIEG |
| **Dane hydrologiczne** (cieki, zbiorniki) | ❌ | `backend/app/sources/bdot.py` – tylko TODO |
| Dane przestrzenne: działki, użytkowanie, ukształtowanie | ✅ | ULDK, IUNG (użytkowanie), NMT (teren, D57) |

## D. Wymagania techniczne (rozdz. 5) i sposób oceny (rozdz. 6)
| Wymaganie | Stan | Gdzie |
|---|---|---|
| Działa dla dowolnej działki w Polsce i dowolnej daty z 10 lat | 🟡 | tak w kodzie; z sieci hackathonu ULDK/NMT blokują – cache, tryb offline, analiza po punkcie (D53–D55, D69) |
| Wynik < 30 s | ✅ | budżet 27 s (D39); z cache 0,04–0,2 s, PDF 1–2 s (`.ai/status/a-backend.md`) |
| Bez płatnych licencji, sprzętu, GIS, programowania | ✅ | przeglądarka; płatnych usług brak – do opisania koszty przy skalowaniu |
| Skalowanie: limity źródeł, aktualizacja, koszty | 🟡 | cache SQLite, bezpiecznik, limity (D44, D45, D53); **opis kosztów i aktualizacji do README** |
| Bezpieczeństwo, bez danych osobowych | ✅ | brak kont i logowania (CLAUDE.md), brak przekierowań i limity odpowiedzi (D56) |
| Dokumentowanie AI | ❌ | do README (B.6) |

## E. Kryteria oceny (rozdz. 7) – czym je pokazujemy
| Kryterium | Waga | Nasze argumenty |
|---|---|---|
| Wartość praktyczna | 25 % | werdykt prostymi zdaniami, „Co tu posiać?”, działania bez pozwoleń najpierw, formalności (Wody Polskie), ekoschematy |
| Dane i wiarygodność | 25 % | NASA vs IMGW (+16–23 %), kalibracja GUS ±7–13 %, test słabej ziemi, ograniczenia i pewność przy każdym wyniku |
| Innowacyjność | 20 % | ranking upraw z symulacji 10 lat dla działki, teren w skali pola, kontrola zgodności opadów |
| Prostota obsługi | 15 % | jeden ekran, bez wyboru uprawy też działa, telefon |
| Prototyp i jakość | 15 % | < 30 s, testy, cache/offline, licencje permisywne; **braki: satelita, hydrologia, README** |

## Najpilniejsze braki (przed oddaniem)
1. **README.md** w katalogu głównym – punkty B.1–B.9 (w tym AI i licencje).
2. **Dane satelitarne** – choćby NDVI/NDMI z Sentinel-2 (Earth Search STAC, CLAUDE.md źródło 9), inaczej wymagana kategoria danych jest pusta.
3. **Dane hydrologiczne** – BDOT10k (rowy, cieki, zbiorniki) albo inne źródło hydrologiczne.
4. Prezentacja PDF (≤ 10 slajdów), film (≤ 3 min), nazwa zespołu.
