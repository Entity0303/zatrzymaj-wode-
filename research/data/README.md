# C2 – dane referencyjne upraw (research)

Dane dla rankingu „Co tu posiać?”. Backend symuluje każdą uprawę na pogodzie z 10 lat (FAO-56 + FAO-33: 1 − Ya/Ym = Ky·(1 − ETa/ETc)) i kalibruje plon potencjalny plonami GUS.
Pobrano i sprawdzono: **2026-11-21**.

| Plik | Co to jest |
|---|---|
| `crops.csv` | 15 upraw IUNG SMSR + 7 gatunków (C2b): Kc, fazy, terminy, Ky, korzenie, p, nawadnianie, płodozmian, gleby, źródła |
| `gus_variables.csv` | zmienna GUS BDL „plon z 1 ha” dla każdej uprawy (sprawdzone na żywo) + osobny wiersz dla braków |
| `gus_yields_woj.csv` | plony dt/ha: 16 województw × 2016–2025 (3149 wierszy) |
| `build_gus.py` | odtwarza oba pliki GUS; odpowiedzi API są zapisane w `gus_raw/`, więc drugi raz GUS nie jest odpytywany |
| `validate.py`, `test_validate.py` | walidacja spójności (`python research/data/validate.py`, `python -m pytest research/data -q`) |

## crops.csv – źródła
- **Kc ini/mid/end, Zr, p**: FAO-56 tab. 12 i 22, te same wartości co `backend/app/analysis/crops.py`. Test sprawdza zgodność Kc z backendem. `root_depth_min/max_m` to zakres z tab. 22, a backend używa jednej wartości z tego zakresu.
- **Fazy (dni)**: proporcje z FAO-56 tab. 11 przeskalowane do okresu od `start_wegetacji` do `typowy_zbior` w PL. Robi to backend (D23, D31), więc liczby są identyczne. Dla ozimych `typowy_siew` to siew jesienny, a fazy liczone są od `start_wegetacji` (wznowienie wegetacji 1 III). Dlatego dodałem kolumnę `start_wegetacji`, której nie było w specyfikacji. Dla wieloletnich siew i zbiór oznaczają początek i koniec sezonu (1 IV–31 X).
- **Ky**: FAO-33 (Doorenbos i Kassam 1979). Oryginału nie miałem. Wartości są z tab. 1 na stronie FAO/IAEA (Moutonnet, https://www.fao.org/4/Y3655E/y3655e04.htm), która przytacza FAO-33. Potwierdzone tam:

  | Uprawa | Ky sezonowy | Fazy |
  |---|---|---|
  | pszenica ozima | 1,00 | 0,2 / 0,6 / 0,5 |
  | kukurydza | 1,25 | – |
  | ziemniak | 1,10 | 0,6 / – / 0,7 / 0,2 |
  | burak cukrowy | 0,80 i 0,90 (dwa wiersze, przyjęto 0,90) | – |
  | fasola | 1,15 | 0,2 / 1,1 / 0,75 / 0,2 |

  Fazy w tabeli mapują się na ini/dev/mid/late (wstrzymanie wody w jednej fazie). Pszenica jara 1,15 jest z zestawienia FAO znalezionego w wyszukiwarce, niezweryfikowana z tabelą.
- **Płodozmian, przerwa, gleby, praktyka nawadniania**: szacunek wg ogólnych polskich zaleceń agrotechnicznych (IUNG-PIB, COBORU, podręczniki szczegółowej uprawy). Nie przepisywałem ich z jednego dokumentu w tej sesji, dlatego w kolumnie `zrodla` są oznaczone „szac.”. Gleby: `iung:` to kategorie podatności IUNG (I = bardzo podatna na suszę … IV), `kompleksy:` to kompleksy przydatności rolniczej (1 pszenny bardzo dobry … 9 zbożowo-pastewny słaby).

### Wartości szacunkowe (szac.) – do weryfikacji przez agronoma
- **Ky rzepaku (0,95), kukurydzy na kiszonkę (1,10), rzepaku – jesień (0,3)**: brak w FAO-33 (rzepak i kiszonka po kalibracji GUS, C3). Rzepak jesień to faza wegetatywna, a jej plon jest w następnym roku, więc w rankingu trzeba użyć `rzepak`.
- **Ky warzyw (0,95), drzew owocowych (0,9), krzewów (0,85), truskawek (1,0), chmielu (0,9), tytoniu (0,9)**: szacunek.
- **`ky_fazy` kukurydzy i zbóż jarych**: szacunek. W sprawdzonej tabeli są tylko wartości sezonowe.
- **Tytoń**: Kc, fazy, Zr i p to założenie backendu, bo w FAO-56 go nie ma.
- **Cała część agrotechniczna**: przerwy, przedplony, gleby i `irrigation_practice`.

## C2b – gatunki zbóż i łubin
- **Nowe wiersze**: `pszenica_ozima`, `zyto`, `pszenzyto_ozime`, `jeczmien_ozimy`, `jeczmien_jary`, `owies`, `lubin`.
- **`group_id`**: backend liczy wodę modelem grupy (`zboza_ozime`, `zboza_jare`, `straczkowe`). Dla upraw bez gatunków `group_id` = `crop_id`. Gatunki nie mają własnego `backend_id`.
- **Fazy gatunków**: proporcje FAO-56 grupy przeskalowane do terminów gatunku (np. jęczmień ozimy zbiór 5 VII, owies 10 VIII), tą samą metodą co w backendzie.
- **`in_ranking`**: `nie` dla `zboza_ozime` i `zboza_jare` (zastąpione przez gatunki) oraz `rzepak_jesien`, `chmiel`, `tyton`. W rankingu jest 17 upraw.
  - `straczkowe` zostaje w rankingu jako groch, bobik i fasola, bo łubin ich nie zastępuje.
- **`wrazliwosc_na_susze`** (niska / srednia / wysoka): nowa kolumna dla wszystkich upraw, szac. Ky zbóż po kalibracji GUS (C3): pszenica, żyto, pszenżyto, jęczmień ozimy 1,00 < jęczmień jary, owies 1,10. `wrazliwosc_na_susze` żyta zostaje „niska” (ocena agronomiczna – pytanie 1 do mentora), ale przewagę żyta w rankingu daje gleba, nie Ky.
- **Ky**: FAO-33 zawiera tylko pszenicę. Ky żyta, pszenżyta, jęczmienia, owsa i łubinu to szacunki, które mają oddawać kolejność wrażliwości, a nie dokładne wartości.
- **Gleby (kompleksy przydatności rolniczej)**:
  - pszenica: odpowiednie 1, 2, 3, 4, 8; nieodpowiednie 5, 6, 7, 9 i kat. IUNG I,
  - żyto: odpowiednie 3–7 oraz kat. I–III,
  - pszenżyto: 2–5, 8,
  - jęczmień: 1, 2, 4, 8 (nie znosi gleb kwaśnych),
  - owies: 4, 5, 8, 9 (znosi gleby kwaśne i wilgotne, nie znosi suchych piasków),
  - łubin: 4–7 i kat. I–II (gleby lekkie i kwaśne).

  Na tej podstawie działa werdykt „na kompleksie 6–7 nie siej pszenicy, siej żyto” (test `test_wheat_vs_rye_soils_and_drought`).
- **Przedplony**: pszenica jest wrażliwa na zboża kłosowe i kukurydzę na ziarno, a owies jest dla niej przedplonem fitosanitarnym. Żyto znosi uprawę po sobie (przerwa 0). Owies wymaga przerwy 3 lat (mątwik owsiany), łubin 4 lat (fuzarioza, antraknoza).
- **GUS**: żyto 4338, pszenżyto 4356 i owies 4350 to plony gatunku ogółem.
  - Formy ozime i jare GUS rozdziela tylko w powierzchni zasiewów (temat P1877), i to nie na poziomie województw. Dlatego `jeczmien_ozimy` i `jeczmien_jary` mają wspólną zmienną 4344 (jęczmień ogółem).
  - **Łubinu nie ma w BDL**: wyszukiwanie „łubin”, „bobik” i „groch” daje 0 zmiennych. Zastępnikiem są rośliny strączkowe razem (47740), oznaczone „ZASTĘPNIK” w `uwagi`.

## C3 – kalibracja Ky z GUS (wpisana 2026-11-21)
- **Zmienione Ky:** żyto 0,80 → 1,00, pszenżyto 0,90 → 1,00, jęczmień ozimy 0,90 → 1,00, owies 1,15 → 1,10, rzepak 1,00 → 0,95, kukurydza na kiszonkę 1,00 → 1,10.
- **Podstawa:** spadki plonów GUS w latach suchych 2015/2018/2019 (`drought_report.md`). W `zrodla` każdej z tych upraw jest dopisek „KY ZMIENIONE (C3…)”.
- **Bez zmian:** Ky zweryfikowane w FAO-33.
- **Tabela dla mentora:** `do_mentora.md`.

## GUS BDL – ograniczenia
- **Ozime i jare**: GUS nie rozdziela form. Dla zbóż ozimych zastępnikiem jest pszenica ogółem (4332), dla jarych jęczmień ogółem (4344).
- **Plon wyliczany**: dla warzyw, drzew i krzewów owocowych oraz truskawek GUS nie publikuje plonu z ha. Wyliczam go jako zbiory / powierzchnia.
- **Krótkie serie**: krzewy i truskawki są dostępne dopiero od 2021 r. (5 lat), a dla drzew owocowych brak 2016 r.
- **Kukurydza na kiszonkę**: zmienna 47749 to plon zielonej masy (~500 dt/ha), nie suchej masy.
- **Chmiel – brak danych**: w BDL nie ma plonu, zbiorów ani powierzchni chmielu na poziomie województw.
- **Tytoń**: nie wszystkie województwa mają dane (uprawa lokalna), jest 125 z 160 wartości.
- **Dane niejawne**: pomijam wartości z `attrId ≠ 1`.
- **Limity API**: anonimowo ok. 10 000 zapytań na 7 dni (nagłówek `X-Rate-Limit`). Skrypt robi przerwę 0,6 s i ponawia zapytanie przy 429.
