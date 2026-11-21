# Wodoskop – prześwietl swoją działkę pod kątem suszy

**HackNation 2026 · zadanie KOWR „Zatrzymaj wodę”**

## Problem
Rolnik nie wie, ile wody ma jego pole, czy susza to wyjątek, czy norma tego miejsca, ani co realnie może zrobić. Dane są publiczne (IMGW, GUGiK, IUNG, GUS, satelity), ale rozproszone i wymagają wiedzy GIS.

## Rozwiązanie
Aplikacja w przeglądarce, bez instalacji, działa też na telefonie.
- **Wejście:** rolnik podaje działkę (numer, klik na mapie albo GPS), uprawę i datę.
- **Wynik w kilka sekund:**
  - **werdykt działki:** jedno zdanie i 4–6 zdań z liczbami (gleba, opady, teren, co siać, a czego nie),
  - **stan wody** w glebie dziś i na tle 10 lat, ryzyko na 7 dni,
  - **„Co tu posiać?”:** ranking 17 upraw policzony na pogodzie z 10 lat (typowy plon, słaby rok, ryzyko suszy, płodozmian),
  - **rekomendacje w kolejności KOWR:** retencja → agrotechnika → nawadnianie, z formalnościami (Wody Polskie) i ekoschematami (ARiMR),
  - **teren:** górki, dołki, kierunki spływu, miejsce, gdzie woda ucieka z pola, propozycje oczka i pasa buforowego,
  - **raport PDF** (werdykt, ranking, źródła, ograniczenia).

## Jak to działa (wszystko liczone, nic nie jest gotowym tekstem)
- **Bilans wody:** model FAO-56 dzień po dniu, ET0 Penman-Monteith, KBW = opad − ET0, pojemność wodna gleby z IUNG.
- **Plon:** FAO-33, 1 − Ya/Ym = Ky·(1 − ETa/ETc). Plon potencjalny z plonów GUS województwa z 10 lat.
- **Teren:** model terenu GUGiK. Wypełnianie zagłębień, kierunki spływu D8 i D-infinity, wskaźnik wilgotności TWI. Własny kod w numpy, bez bibliotek GPL.
- **Gleba:** kategoria IUNG, mapa glebowo-rolnicza GUGiK (kompleks, gatunek), SoilGrids (uziarnienie, przepuszczalność).
- **Rekomendacje:** reguły YAML (warunek → zalecenie → dane, które je uruchomiły). LLM nic nie liczy.

## Dane i wiarygodność – co sprawdziliśmy sami
- **Opady z kilku źródeł.** Porównaliśmy model satelitarny NASA POWER (siatka ~50 km) ze stacjami IMGW (posterunki opadowe, klimatologiczne i synoptyczne, ważenie odległością) na 4 działkach w 4 województwach, 2016–2025:
  - **NASA zawyża opad o 16–23 % rocznie na nizinach, w każdym z 10 lat**, a w górach jest blisko stacji (−3 %),
  - lokalnej burzy NASA nie widzi: **15.07.2021 na Podlasiu stacja IMGW zmierzyła 58 mm, NASA podaje 3,5 mm**,
  - wniosek: **IMGW głównym źródłem opadu** (wdrażane w backendzie – A7), a modele służą do porównania. Rolnik dostaje jedno zdanie, czy źródła są zgodne.
- **Kalibracja z GUS.**
  - Model wody i plonu porównany ze średnimi plonami GUS z 10 lat: **różnica od −13 % do +11 % (±7–13 %)** dla upraw polowych w województwach podlaskim, lubelskim i wielkopolskim.
  - Wrażliwość upraw na suszę sprawdziliśmy na spadkach plonów GUS w latach suchych 2015, 2018 i 2019.
  - Uczciwie: GUS miesza efekt gatunku z efektem gleby (żyto rośnie na najsłabszych piaskach), więc kalibracja jest tylko kierunkowa. Glebę model liczy osobno.
- **Test słabej ziemi.** Puszcza Notecka (piasek słabogliniasty, kompleks żytni słaby, kat. IUNG I): **❌ nie siej pszenicy ani rzepaku, ✅ siej żyto i łubin.** Wynik zgodny z agrotechniką i potwierdzony też na piaskach Kurpi.
- **Przy każdym wyniku:** źródło, data danych, ograniczenia i pewność. Braki danych mówimy wprost (np. „obszar przybliżony – brak granic działki”).

## Innowacyjność
- **Werdykt i ranking upraw** z symulacji 10 lat pogody dla konkretnej działki, a nie średnia dla gminy.
- **Teren w skali pola:** gdzie woda ucieka i gdzie warto ją zatrzymać (oczko, pas buforowy).
- **Kontrola zgodności opadów** z 3 niezależnych źródeł zamiast ślepego zaufania jednemu modelowi.

## Ograniczenia (mówimy wprost)
- **Rozdzielczość:** siatka terenu 3–15 m, gleby z map 1:25 000 sprzed lat.
- **Czego model nie zna:** drenażu, rowów ani przepustów.
- **Wartości szacunkowe:** Ky części upraw i część zaleceń agrotechnicznych. Oznaczone w danych, czekają na weryfikację agronoma.
- **Niezawodność usług publicznych:** usługi GUGiK i Open-Meteo bywają przeciążone, dlatego mamy cache i tryb offline dla demo.

## Technologia i licencje
- **Backend:** Python, FastAPI, numpy, WeasyPrint.
- **Frontend:** React, Vite, Leaflet.
- **Uruchomienie:** `docker compose up`.
- **Licencje:** tylko permisywne (MIT/BSD/Apache, czcionka Inter – OFL). Żadnych danych osobowych.

## Zespół
- **A – Dominik:** backend.
- **B – Mefju:** frontend.
- **C – Mikołaj:** badania i dane – teren, uprawy, GUS, opady, działki demo.
