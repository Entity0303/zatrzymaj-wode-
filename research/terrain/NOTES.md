# C1 – prototyp analizy terenu i spływu (research)

Osobny skrypt badawczy, nie jest częścią aplikacji. Czysty Python + numpy (bez GPL: bez pysheds/richdem).
Pliki: `terrain.py` (moduł), `run_examples.py` (działki testowe + PNG), `test_terrain.py` (testy bez sieci), `out/` (wyniki).

## Metoda
1. ULDK → obrys (EPSG:2180). Siatka = obrys + bufor 100 m, krok ≈ 5·pow[ha]^0,37 m (1 ha → 5 m, 20 ha → 15 m), maks. 6000 pkt (≤ 6 POST po 1000, równolegle).
2. NMT GUGiK, POST `GetHByPointList` (x = PÓŁNOC, y = WSCHÓD). Twardy limit czasu i rozmiaru odpowiedzi, ponowienia. Wartości 0,0 = brak danych, piki (>25 m od mediany sąsiadów) usuwane, braki uzupełniane z sąsiadów.
3. Wygładzenie Gaussa σ = 6 m (szum kwantyzacji 0,1 m), potem spadek i ekspozycja metodą Horna, a do tego TPI (okno 40 m) i krzywizna.
4. Priority-flood (Barnes 2014) daje wypełniony DEM, zagłębienia (głębokość, powierzchnia, objętość, zlewnia) i porządek topologiczny.
5. D8 (najstromszy spadek; na płaskich kierunek z priority-flood) i akumulacja. D-infinity (Tarboton) do TWI = ln(a / tan β).
6. Wyjścia wody to komórki działki, których odbiorca D8 leży poza nią, grupowane w skupiska. Liczymy udział działki odprowadzany przez każde skupisko i kierunek. Liczymy też dopływ spoza działki.
7. Propozycje:
   - oczko w największym zagłębieniu: objętość dopływu z 20 mm brutto oraz ze współczynnikiem spływu 0,3, sugerowana powierzchnia przy głębokości 1,5 m. Gdy zagłębienia brak, oczko przy głównym wyjściu wody.
   - pas buforowy 10 m w poprzek głównego kierunku spływu, gdy spadek > 5 % na ≥ 10 % działki (kolejny co 120 m stoku).

## Progi i dlaczego
| Próg | Wartość | Dlaczego |
|---|---|---|
| stok / płasko | 3 % | poniżej ~2–3 % spływ powierzchniowy słaby; szum NMT po wygładzeniu ≈ 0,5 % |
| sucha górka | TPI ≥ +0,3 m i wypukło | 3× precyzja NMT; wypukłe szczyty przesychają najszybciej |
| mokry dołek | zagłębienie, albo TPI ≤ −0,3 m, albo TWI ≥ 11 (przy spadku < 3 %) | zbieżny spływ / brak odpływu |
| zagłębienie | głęb. ≥ 0,2 m, pow. ≥ 50 m² | 2× precyzja NMT – płytsze to szum |
| wyjście wody | ≥ 5 % działki | mniejsze to drobne rozlewy na krawędzi |
| pas buforowy | spadek > 5 % na ≥ 10 % działki | od ~5 % rośnie ryzyko erozji i szybkiego odpływu |

## Wyniki (pomiar 2026-11-21, sieć domowa)
| Działka | pow. | krok | spadek śr/maks | Δh | zagłębienia | wyjście wody | propozycje | czas [s] (ULDK/NMT/obl./razem) |
|---|---|---|---|---|---|---|---|---|
| 201305_2.0038.6/1 | 0,58 ha | 4,5 m | 3,1 / 6,1 % | 2,0 m | 0 | SW, 100 % | oczko przy odpływie | 4,5 / 5,2 / 0,13 / 9,8 |
| 061704_2.0011.383/2 | 0,21 ha | 4,0 m | 2,9 / 5,0 % | 2,9 m | 0 | N, 80 % | oczko przy odpływie | 4,6 / 4,2 / 0,08 / 8,9 |
| 040703_5.0020.76 | 6,82 ha | 10,5 m | 0,8 / 3,3 % | 1,7 m | 1 (662 m³) | NE, 75 % | oczko w zagłębieniu | 0,2 / 2,8 / 0,06 / 3,1 |
| 121601_5.0002.770 (stok, małopolskie) | 3,62 ha | 8,5 m | 15,2 / 41,3 % | 39,2 m | 0 | S, 76 % | oczko przy odpływie + pas buforowy | 5,1 / 4,5 / 0,08 / 9,7 |

Szczegóły: `out/<id>.facts.json`, `out/<id>.geojson`, `out/<id>_{1_wysokosci,2_spadki,3_strefy,4_splyw,5_propozycje,przeglad}.png`, `out/summary.json`.
Działkę na stoku znaleziono przez ULDK `GetParcelByXY` (20.94, 49.73). IUNG daje kod 3, czyli grunt rolny.

Czas: wszystkie działki zmieściły się w ≤ 10 s. Obliczenia trwają < 0,2 s, resztę zabiera sieć. ULDK czasem zawiesza połączenie (timeout 4 s i ponowienie dają ~4,5 s), a NMT co jakiś czas zwraca odpowiedź-śmieć (setki MB). Wtedy przerywamy i ponawiamy. W aplikacji cache obrysu z ULDK (backend i tak go pobiera) skróci czas do ~3–5 s.

## Ograniczenia
- Rozdzielczość siatki 3–15 m: bruzdy, koleiny, rowki i małe oczka są niewidoczne. Wysokości co 0,1 m, więc przy spadkach < 1 % kierunek spływu jest niepewny.
- Bufor 100 m: długie stoki spoza bufora nie wchodzą do zlewni, więc dopływ jest niedoszacowany. Wyjście wody liczone jest na krawędzi działki.
- Wygładzenie spłaszcza płytkie zagłębienia (σ to parametr `smooth_sigma_m`).
- Brak danych o drenażu, rowach, przepustach, drogach i kierunku orki. Objętości to szacunek rzędu wielkości.
- Pas buforowy to prosta linia prostopadła do głównego kierunku. Lepiej byłoby poprowadzić go po warstwicy (następny krok).

## Do przeniesienia do aplikacji
- `backend/app/sources/nmt.py` ← `fetch_heights`, `_nmt_chunk`, `http_request` (przepisać na httpx async), `despike`, `fill_nans`.
- `backend/app/analysis/terrain.py` ← `analyze_surface` i funkcje rastrowe (bez zmian, czysty numpy). Projekcję można zastąpić `core/geo.py`.
- Interfejs: `terrain_facts(parcel_geom) -> dict` (fakty do reguł), `terrain_layers(parcel_geom) -> GeoJSON` (EPSG:4326, właściwość `layer`: parcel, zone, depression, flow_arrow, flow_path, outlet, inlet, hill_top, proposal).
