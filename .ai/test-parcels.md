# Działki testowe

Do ręcznych testów i testów „live”. Kolumna „Sprawdzone” = co potwierdziliśmy na żywo (data); pozostałe cechy podał właściciel repo – zweryfikować przy pracy nad danym źródłem i uzupełnić.

| Działka | Gdzie | Cechy / czego oczekujemy | Sprawdzone |
|---|---|---|---|
| `201305_2.0038.6/1` | podlaskie, pow. wysokomazowiecki, gm. Kobylin-Borzymy, obręb Wnory-Wandy | grunt rolny; klasy EGiB RIIIb / RIVa / RIVb | ULDK ✓ 2026-11-21: działka 6/1, ~0,58 ha (test `test_live_uldk_parcel`) |
| `061704_2.0011.383/2` | lubelskie | klasy EGiB RIIIa / PsIII | — |
| `040703_5.0020.76` | kujawsko-pomorskie | brak klas w EGiB → ograniczenie „Klasy bonitacyjne niedostępne w tym powiecie” | — |
| `302114_5.0018.445` | wielkopolskie | — | — |
| `160703_5.0011.945` | opolskie | kontur Ls (las) | — |
| `143203_2.0027.112/11` | mazowieckie, pow. warszawski zachodni, gm. Kampinos, obręb Szczytno | IUNG kod 11 (las) → komunikat „to nie jest grunt rolny” | ULDK ✓ 2026-11-21: działka 112/11, ~5,01 ha |

## Wyszukiwanie po nazwie obrębu

| Zapytanie | Oczekiwane | Sprawdzone |
|---|---|---|
| „Szczytno 112/11” | wyszukanie przez GetParcelByIdOrNr | ✓ 2026-11-21: **1 wynik** (143203_2.0027.112/11) – nie lista |
| „Wola 1” | wiele wyników → HTTP 409, lista + numerowane znaczniki | ✓ 2026-11-21: 5 działek (Rogowo, Biłgoraj, Czerwińsk n. Wisłą, Kisielice, Kozłowo) |
| „Nieistniejacy 1/1” | 404 → „Nie znaleziono działki” | ✓ 2026-11-21 |
