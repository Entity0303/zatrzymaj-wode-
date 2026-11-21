# C2 – dane referencyjne upraw (research)

Dane dla rankingu „Co tu posiać?”. Backend symuluje każdą uprawę na pogodzie z 10 lat (FAO-56 + FAO-33: 1 − Ya/Ym = Ky·(1 − ETa/ETc)) i kalibruje plon potencjalny plonami GUS.
Pobrano i sprawdzono: **2026-11-21**.

| Plik | Co to jest |
|---|---|
| `crops.csv` | 15 upraw IUNG SMSR: Kc, fazy, terminy, Ky, korzenie, p, nawadnianie, płodozmian, gleby, źródła |
| `gus_variables.csv` | zmienna GUS BDL „plon z 1 ha” dla każdej uprawy (sprawdzone na żywo) + osobny wiersz dla braków |
| `gus_yields_woj.csv` | plony dt/ha: 16 województw × 2016–2025 (2029 wierszy) |
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
- **Ky rzepaku (1,0), kukurydzy na kiszonkę (1,0), rzepaku – jesień (0,3)**: brak w FAO-33. Rzepak jesień to faza wegetatywna, a jej plon jest w następnym roku, więc w rankingu trzeba użyć `rzepak`.
- **Ky warzyw (0,95), drzew owocowych (0,9), krzewów (0,85), truskawek (1,0), chmielu (0,9), tytoniu (0,9)**: szacunek.
- **`ky_fazy` kukurydzy i zbóż jarych**: szacunek. W sprawdzonej tabeli są tylko wartości sezonowe.
- **Tytoń**: Kc, fazy, Zr i p to założenie backendu, bo w FAO-56 go nie ma.
- **Cała część agrotechniczna**: przerwy, przedplony, gleby i `irrigation_practice`.

## GUS BDL – ograniczenia
- **Ozime i jare**: GUS nie rozdziela form. Dla zbóż ozimych zastępnikiem jest pszenica ogółem (4332), dla jarych jęczmień ogółem (4344).
- **Plon wyliczany**: dla warzyw, drzew i krzewów owocowych oraz truskawek GUS nie publikuje plonu z ha. Wyliczam go jako zbiory / powierzchnia.
- **Krótkie serie**: krzewy i truskawki są dostępne dopiero od 2021 r. (5 lat), a dla drzew owocowych brak 2016 r.
- **Kukurydza na kiszonkę**: zmienna 47749 to plon zielonej masy (~500 dt/ha), nie suchej masy.
- **Chmiel – brak danych**: w BDL nie ma plonu, zbiorów ani powierzchni chmielu na poziomie województw.
- **Tytoń**: nie wszystkie województwa mają dane (uprawa lokalna), jest 125 z 160 wartości.
- **Dane niejawne**: pomijam wartości z `attrId ≠ 1`.
- **Limity API**: anonimowo ok. 10 000 zapytań na 7 dni (nagłówek `X-Rate-Limit`). Skrypt robi przerwę 0,6 s i ponawia zapytanie przy 429.
