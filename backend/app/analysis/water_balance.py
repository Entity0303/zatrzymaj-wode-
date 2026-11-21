"""Bilans wody: KBW = opad − ET0 oraz model wody w glebie FAO-56 („bucket”).

TODO (osoba A):
- KBW dobowy i narastająco od początku sezonu (1 III), pasmo min/max/średnia z 10 lat,
- model wody w glebie: pojemność = WOD gleby (analysis/soil.py) × głębokość korzeni,
  ETc = Kc × ET0, % wody dostępnej, dni stresu w każdym z 10 lat,
- „stres za X dni” z prognozy Open-Meteo,
- tylko dane sprzed daty analizy.
"""
