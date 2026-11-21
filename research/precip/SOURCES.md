# C4 – źródła opadów sprawdzone na żywo (2026-11-21)

| Źródło | Endpoint | Czas | Co daje | Ograniczenia |
|---|---|---|---|---|
| IMGW – archiwum dobowe OPAD | `danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/opad/{rok}/{rok}_{MM}_o.zip` | ~0,1 s / plik (~40 kB, cała Polska, 1 miesiąc) | posterunki opadowe – najgęstsza sieć (~575 posterunków w VI 2018) | CSV w cp1250, bez nagłówka; statusy: 8 = brak pomiaru, 9 = brak zjawiska (0), Z = opad zbiorczy za kilka dni; brak dnia w miesiącu = 0 mm; **brak współrzędnych** w `wykaz_stacji.csv` |
| IMGW – archiwum KLIMAT | `.../dobowe/klimat/{rok}/{rok}_{MM}_k.zip` | ~0,1 s / plik | stacje klimatologiczne (opad SMDB w kol. 14) | jw. |
| IMGW – archiwum SYNOP | `.../dobowe/synop/{rok}/{rok}_{nr}_s.zip` | ~0,1 s / plik | ~60 stacji synoptycznych, najlepsza jakość | plik roczny na stację; numer = 3 ostatnie cyfry kodu (WMO 12xxx) |
| IMGW – API bieżące `/api/data/synop` | `danepubliczne.imgw.pl/api/data/synop` | 0,12 s | 62 stacje, `suma_opadu` z ostatniej godziny pomiaru | bez współrzędnych, tylko stan bieżący |
| IMGW – API bieżące `/api/data/meteo` | `danepubliczne.imgw.pl/api/data/meteo` | 0,9 s (0,5 MB) | 788 stacji telemetrycznych **z `lon`/`lat`**, 699 z `opad_10min` | tylko bieżące 10 min; służy nam jako **katalog współrzędnych** stacji archiwalnych (ten sam 9-cyfrowy kod) |
| ERA5-Land | `archive-api.open-meteo.com/v1/archive?…&daily=precipitation_sum&models=era5_land` | patrz `data/cache/*_seconds` | reanaliza ~9 km, 10 lat w 1 zapytaniu | limit dzienny na IP (w sieci hackathonu 429) – zapisujemy odpowiedzi w `data/cache/`, ponawiamy z przerwą |
| NASA POWER | `power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR&community=AG` | patrz `data/cache/*_seconds` | siatka ~50 km, 10 lat w 1 zapytaniu (jak backend) | wygładzone opady – lokalne burze niewidoczne; ostatnie 2–4 dni = −999 |
| Prognoza wielomodelowa | `api.open-meteo.com/v1/forecast?…&daily=precipitation_sum&models=icon_seamless,ecmwf_ifs025,gfs_seamless` | 0,35 s | **kilka modeli w JEDNYM zapytaniu** – pola `precipitation_sum_<model>` | rozrzut modeli = niepewność prognozy |

**Współrzędne stacji.** Archiwum IMGW nie ma współrzędnych. 9-cyfrowy kod koduje tylko kwadrat 1°×1° (np. `249199978` → 49°N, 19°E). Współrzędne biorę z API `/api/data/meteo`, które je podaje dla 788 stacji z tym samym kodem. W VI 2018 r. pokrywało to 261 z 575 posterunków opadowych. Pozostałych stacji bez współrzędnych nie używam.
