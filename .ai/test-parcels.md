# Działki testowe

Do ręcznych testów i testów „live” (`pytest -m live`). Wartości zweryfikowane na żywo 2026-11-21 (ULDK, IUNG WCS 5 m, KIEG).
Kody IUNG: 1–4 kategorie podatności (I bardzo podatna … IV mało podatna), 5 gleby organiczne, 11 las, 12 woda, 13 zabudowa, 14 drogi/nieużytki.

| Działka | Gdzie, pow. | IUNG: dominująca · udziały | WOD | Klasy EGiB | Grunt nierolny |
|---|---|---|---|---|---|
| `201305_2.0038.6/1` | podlaskie, gm. Kobylin-Borzymy, obręb Wnory-Wandy · 0,58 ha | III · III 75%, I 25% | 166 mm | RIIIb, RIVa, RIVb | nie |
| `061704_2.0011.383/2` | lubelskie, gm. Rybczewice · 0,21 ha | IV · IV 52%, III 48% | 203 mm | RIIIa, PsIII | nie |
| `040703_5.0020.76` | kujawsko-pomorskie, gm. Gniewkowo, obręb Szadłowice · 6,82 ha | III · III 90%, IV 10% | 189 mm | **brak** (powiat nie udostępnia) | nie |
| `302114_5.0018.445` | wielkopolskie, gm. Stęszew · 83,1 ha | **12 (woda) 100%** | – (nie dotyczy) | brak | **tak – woda** |
| `160703_5.0011.945` | opolskie, gm. Korfantów · 22,0 ha | **11 (las) 100%** | – (nie dotyczy) | Ls | **tak – las** |
| `143203_2.0027.112/11` | mazowieckie, gm. Kampinos, obręb Szczytno · 5,01 ha | **11 (las) 51%**, II 23%, zabudowa 14%, IV 12% | – (nie dotyczy; mineralna część 172 mm) | brak | **tak – las** (nierolne łącznie 65%) |

Czas gleby (ULDK + IUNG + KIEG równolegle): 0,5–0,8 s na działkę (pierwsze zapytanie w sesji ~3,9 s – zimne połączenia).
Pogoda/bilans (A1, live): `201305_2.0038.6/1`, data 15.07.2018 – bilans 1.03–14.07 −145,1 mm vs średnia 2008–2017 −39,2 mm (niższy tylko w 1 z 10 lat); NASA POWER 1,84 s.

## Wyszukiwanie po nazwie obrębu

| Zapytanie | Wynik (sprawdzone 2026-11-21) |
|---|---|
| „Szczytno 112/11” | **1 wynik** (143203_2.0027.112/11) – nie lista |
| „Wola 1” | 5 działek → HTTP 409, lista + numerowane znaczniki (Rogowo, Biłgoraj, Czerwińsk n. Wisłą, Kisielice, Kozłowo) |
| „Nieistniejacy 1/1” | 404 → „Nie znaleziono działki” |

## `GET /api/search` (A5c) – sprawdzone 2026-11-21 (ULDK blokowany – 302; PRNG i Nominatim działały)

| `q` | Rozpoznano jako | Wynik | Czas (zimny cache → cache) |
|---|---|---|---|
| `201305_2.0038.6/1` | parcel_id | 1 działka (znana, bez ULDK) | 0,05 s |
| `Wnory-Wandy 6/1` | obreb_numer | 1 działka (zapas: znane działki, ULDK 302) | 4,2 s (ponowienia ULDK) → 0,0 s |
| `Tczów` | name | 1 miejscowość PRNG: Tczów, gm. Tczów, pow. zwoleński, mazowieckie (21,4458 E, 51,3261 N) | 2,3 s → 0,0 s |
| `Tczów 123` | obreb_numer | ULDK niedostępne → miejscowość Tczów + podpowiedź „ewidencja działek nie odpowiada” (**do sprawdzenia na żywo z innej sieci**: czy działka 123 istnieje w obrębie Tczów) | 0,0–0,35 s |
| `Nowa Wieś` | name | 190 miejscowości (lista 10 z gminami, `truncated`, „dopisz gminę”) | 2,5–5,7 s → 0,0 s |
| `Nowa Wieś, Busko` | name | 1: gm. Busko-Zdrój, pow. buski, świętokrzyskie | 4,3 s |
| `Brzezno` / `Brzeźno` | name | 37 miejscowości (bez ogonków – szeroki wzorzec) | 2,8–4,7 s |
| `xyzabc` | name | 0 wyników, 200 + podpowiedź | 4–6 s (PRNG ścisły + szeroki + Nominatim) |
| pole narysowane 3,6 ha (Puszcza Notecka) | `POST /api/analysis` | `narysowane_9d6cec913e`, gm. Wronki (Nominatim), „Słaba, sucha działka…” | 1,1 s |


## `GET /api/search` na żywo (A8) – 2026-11-22, ULDK przez VPN

| `q` | Rozpoznano jako | Wynik | Czas |
|---|---|---|---|
| `Tczów Borki 279` | obreb_numer | 1 działka: **143604_2.0011.279**, gm. Tczów, pow. zwoleński, mazowieckie, 2,14 ha | 0,3 s |
| `Tczów 123` | obreb_numer | brak działki 123 w obrębie „Tczów” (ULDK odpowiedział) → miejscowość Tczów (PRNG) + podpowiedź „przybliż mapę i kliknij swoje pole” | 0,1 s |

## Działki demo (A8) – `app/data/demo_parcels.json`

| Id | Gdzie | Gleba (IUNG) | Teren (NMT) | Werdykt |
|---|---|---|---|---|
| 201305_2.0038.6/1 | Wnory-Wandy, gm. Kobylin-Borzymy | kat. III, WOD 166 mm | stok 56%, płasko 12%, obniżenie 32% | Dobra działka z wilgotnym obniżeniem |
| 302408_5.0017.70/4 | Pożarowo, gm. Wronki (Puszcza Notecka) | kat. I, 120 mm | górka 18%, stok 33%, płasko 35%, obniżenie 14% | Słaba, sucha działka – siej rośliny odporne na suszę |
| 141505_2.0011.1125/2 | Kadzidło (Kurpie) | kat. II, 139 mm | płasko 68%, obniżenie 27% | Słaba, sucha działka |
| 060401_1.0268.421 | Sławęcin, gm. Hrubieszów | kat. IV, 219 mm | górka 26%, stok 37%, płasko 36% | Dobra ziemia, ale w suche lata brakuje wody |
| 040704_2.0019.57 | Krusza Duchowna, gm. Inowrocław | kat. III, 186 mm | płasko 86%, obniżenie 14% | Dobra ziemia, ale w suche lata brakuje wody |
| 061408_5.0008.203 | Drzewce-Kolonia, gm. Nałęczów (less) | kat. III | górka 37%, stok 49%, płasko 14% | Dobra ziemia, ale w suche lata brakuje wody |
| 281003_2.0015.79/5 | Muntowo, gm. Mrągowo | kat. II, 173 mm | górka 36%, stok 49%, obniżenie 14% | Słaba, piaszczysta działka |
| 220907_5.0001.162 | Brzózki, gm. Nowy Staw (Żuławy) | kat. II, 106 mm | płasko 56%, obniżenie 43% | Słaba, sucha działka |
| 181605_2.0001.1552/2 | Bachórz, gm. Dynów | kat. III, 190 mm | górka 16%, stok 78%, płasko 6% | Dobra ziemia, ale w suche lata brakuje wody |
| 061704_2.0011.383/2 | Stryjno Kolonia, gm. Rybczewice | kat. IV, 203 mm | stok 49%, płasko 47%, obniżenie 4% | Dobra ziemia, ale w suche lata brakuje wody |
| 143203_2.0027.112/11 | Szczytno, gm. Kampinos | las (51%) | górka 12%, stok 34%, płasko 42%, obniżenie 12% | to nie jest grunt rolny |
| 143203_2.0027.126/3 | Szczytno, gm. Kampinos | kat. III, 179 mm | płasko 83%, obniżenie 17% | Dobra ziemia, ale w suche lata brakuje wody |
| 142803_2.0025.118 | Lasotka, gm. Iłów | kat. II, 164 mm | płasko 87%, obniżenie 12% | Słaba, sucha działka |
| 040703_5.0020.76 | Szadłowice, gm. Gniewkowo | kat. III, 189 mm | płasko 88%, obniżenie 11% | Dobra ziemia, ale w suche lata brakuje wody |
| 121601_5.0002.770 | Bruśnik, gm. Ciężkowice | kat. III, 186 mm | górka 65%, stok 35% | Dobra działka z suchą górką |
