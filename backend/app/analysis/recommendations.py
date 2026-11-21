"""Silnik reguł: warunek -> rekomendacja -> dane, które ją uruchomiły.

Reguły w analysis/rules/*.yaml. Kolejność kategorii: retencja -> agrotechnika -> nawadnianie.
Żadnych gotowych tekstów bez liczb – opis wypełniany wartościami z analizy. LLM nie liczy niczego.

TODO (osoba A): wczytanie YAML, ewaluacja warunków na wynikach analizy, maks. 3 w panelu,
`inputs` (Evidence) i `confidence` dla każdej rekomendacji, geometria miejsca (np. zagłębienie).
"""
