"""GUS BDL API – plony i ceny skupu wg województw (CLAUDE.md, źródło 11; funkcja P3).

https://bdl.stat.gov.pl/api/v1  /data/by-variable/{id}?unit-level=2&year=...&format=json
Np. zmienna 4332 = plony pszenicy dt/ha; temat P2967 = miesięczne ceny pszenicy zł/dt.

TODO (osoba A): kontekst „w roku suszy 2018 plony w województwie były o X% niższe” (SPEC 7.B).
"""

SOURCE = "GUS BDL"
