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
