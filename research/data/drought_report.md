# C3b – wrażliwość na suszę wg GUS (2015, 2018, 2019)

Skrypt: `drought.py`.
- **Wejście:** `gus_yields_woj.csv` za 2016–2025 oraz rok 2015 dociągnięty z BDL (cache w `gus_raw/`).
- **Dane szczegółowe:** `drought_sensitivity.csv` (uprawa × województwo × rok suchy).
- **Podsumowanie:** `drought_summary.csv`.
- **Spadek** = (średnia 2016–2025 − plon) / średnia. Dodatkowo liczę spadek względem trendu liniowego 2016–2025 dla każdego województwa, bo plony rosną w czasie, a 2018–2019 wypadają na początku serii.
- **`crops.csv`**: skrypt go nie zmienia. Propozycję z sekcji niżej wpisałem ręcznie po zatwierdzeniu.

## Ranking (od najbardziej wrażliwych, spadek względem trendu, 16 woj. × 3 lata)
| # | Uprawa | spadek vs trend | vs średnia 10 l. | 2018 | Ky przed C3 | Ky wg prostej |
|---|---|---|---|---|---|---|
| 1 | ziemniak | 17,2 % | 21,1 % | 12,2 % | 1,10 ✔ | 1,19 |
| 2 | kukurydza na ziarno | 16,3 % | 21,1 % | 13,4 % | 1,25 ✔ | 1,17 |
| 3 | kukurydza na kiszonkę | 13,3 % | 14,2 % | 8,0 % | 1,00 | 1,12 |
| 4 | strączkowe (= łubin) | 9,4 % | 15,0 % | 12,8 % | 1,15 ✔ / 1,00 | 1,06 |
| 5 | owies | 8,6 % | 16,6 % | 22,0 % | 1,15 | 1,04 |
| 6 | warzywa | 7,9 % | 5,1 % | 2,1 % | 0,95 | 1,03 |
| 7 | jęczmień (ozimy = jary) | 7,1 % | 16,8 % | 21,9 % | 0,90 / 1,10 | 1,02 |
| 8 | burak cukrowy | 6,7 % | 8,7 % | 3,5 % | 0,90 ✔ | 1,01 |
| 9 | pszenżyto | 6,4 % | 16,2 % | 20,7 % | 0,90 | 1,01 |
| 10 | żyto | 5,9 % | 15,7 % | 20,9 % | 0,80 | 1,00 |
| 11 | pszenica | 4,4 % | 13,5 % | 18,8 % | 1,00 ✔ | 0,97 |
| 12 | rzepak | 3,2 % | 12,3 % | 16,7 % | 1,00 | 0,95 |

✔ = Ky potwierdzone w FAO-33. Na tych 5 uprawach dopasowałem prostą Ky = 0,897 + 0,0169 · spadek.
- Drzewa owocowe nie nadają się do kalibracji: w 2019 r. spadek wynosi 31 %, głównie przez przymrozki, a w serii brak 2016 r.
- Krzewy i truskawki mają dane dopiero od 2021 r., więc w serii nie ma lat suchych.

## Wnioski
1. **Kolejność zgadza się tylko częściowo.** Korelacja Spearmana między spadkiem a Ky z `crops.csv` wynosi **0,64**. Okopowe i kukurydza są na górze w GUS i mają wysokie Ky. Rzepak i pszenica są na dole.
2. **Żyto nie wypada jako mniej wrażliwe od pszenicy.** W 2018 r. spadek żyta był większy niż pszenicy w 14 z 16 województw. To najpewniej efekt selekcji gleb: żyto rośnie na lekkich glebach (kompleksy 5–7, kat. IUNG I–II), które w suszy tracą najwięcej. Średnie wojewódzkie nie pozwalają oddzielić wpływu gatunku od wpływu gleby. Wniosek dla werdyktu „siej żyto, nie pszenicę”: przewagę żyta trzeba opierać na **glebie** (tylko żyto daje plon na kompleksach 6–7), a nie na niższym Ky.
3. **Rzepak ma najmniejszy spadek.** Kiszonka jest bliżej kukurydzy na ziarno niż przypuszczałem. Owies jest najbardziej wrażliwym zbożem, co zgadza się z naszą kolejnością.
4. **Ograniczenia GUS:**
   - jęczmień ozimy i jary to jedna seria,
   - łubin ma serię strączkowych razem,
   - warzywa to suma wielu gatunków, często nawadnianych, więc sygnał jest słaby,
   - średnia wojewódzka zaciera różnice między glebami.

   Prosta z 5 punktów jest słabo dopasowana i ściska Ky do zakresu 0,95–1,19. Traktuję ją jako kierunek zmian, nie jako wartości.

## Ograniczenie kalibracji
**GUS nie rozdziela efektu gatunku od efektu gleby, więc kalibracja jest tylko kierunkowa.** Średnie wojewódzkie łączą gatunek z glebą, na której zwykle rośnie: żyto i pszenżyto rosną głównie na najsłabszych piaskach, więc w suszy tracą dużo przez glebę, nie przez gatunek. Model backendu liczy glebę osobno (WOD z IUNG). Gdyby Ky żyta podnieść według GUS, model ukarałby żyto za piasek drugi raz i zepsułby werdykt „na piasku siej żyto, nie pszenicę”. Pytanie o żyto zostaje do mentora (`do_mentora.md`, pytanie 1).

## Propozycja poprawionych Ky – wpisana do crops.csv 2026-11-21, żyto i pszenżyto cofnięte
| Uprawa | teraz | proponuję | dlaczego |
|---|---|---|---|
| żyto | 0,80 | ~~1,00~~ **0,80 – cofnięte** | GUS miesza gatunek z glebą (żyto na najsłabszych piaskach); backend liczy glebę osobno (WOD) |
| pszenżyto ozime | 0,90 | ~~1,00~~ **0,90 – cofnięte** | jak żyto |
| jęczmień ozimy | 0,90 | **1,00** | GUS: jedna seria z jarym, spadek > pszenica |
| owies | 1,15 | **1,10** | GUS: najbardziej wrażliwe zboże, ale bliżej jęczmienia |
| rzepak | 1,00 | **0,95** | GUS: najmniejszy spadek |
| kukurydza na kiszonkę | 1,00 | **1,10** | GUS: blisko kukurydzy na ziarno |
| pszenica, kukurydza na ziarno, ziemniak, burak, strączkowe | – | bez zmian | FAO-33 |
| jęczmień jary, łubin, warzywa, owoce, chmiel, tytoń | – | bez zmian | GUS nie rozróżnia albo brak danych |
