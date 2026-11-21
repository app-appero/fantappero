"""Riparazione dei nomi dei calciatori salvati con la codifica rovinata (QA 20-21/11).

Quattro nomi del listone di dev erano arrivati dal fornitore come testo UTF-8 decodificato
una seconda volta ("L. JovanoviÄ\\x87" invece di "L. Jovanović") e la ricerca senza accenti
non li trovava. Le sincronizzazioni ora salvano i nomi riparati (`repair_mojibake`); questa
funzione ripara subito quelli già salvati, senza aspettare la prossima sincronizzazione.

Idempotente: tocca solo i nomi che `repair_mojibake` cambia, cioè le sequenze UTF-8 valide
lette come Latin-1/Windows-1252. Un nome già giusto resta com'è, quindi un secondo passaggio
non trova più niente.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.text_folding import repair_mojibake
from sports_data.roster.models import Athlete

#: Campi del calciatore con un nome da riparare.
REPAIRABLE_NAME_FIELDS = ("canonical_name", "first_name", "last_name")

# Una sequenza rovinata comincia sempre con un carattere tra "Â" (U+00C2) e "ô" (U+00F4):
# il filtro in SQL evita di leggere tutto il catalogo, la decisione la prende Python. I
# caratteri sono elencati uno per uno: un intervallo nella regex può dipendere dalla collation.
_SUSPICIOUS_PATTERN = "[" + "".join(chr(code) for code in range(0xC2, 0xF5)) + "]"


@dataclass(frozen=True)
class RepairedAthleteName:
    """Un nome riparato (o da riparare, in prova)."""

    athlete_id: UUID
    provider_id: int
    field: str
    before: str
    after: str


def repair_athlete_names(session: Session, *, dry_run: bool = False) -> list[RepairedAthleteName]:
    """Ripara i nomi dei calciatori con la codifica rovinata; con ``dry_run`` li elenca soltanto.

    Non fa commit: lo decide il chiamante.
    """
    columns = [getattr(Athlete, field) for field in REPAIRABLE_NAME_FIELDS]
    rows = session.scalars(
        select(Athlete)
        .where(or_(*(column.regexp_match(_SUSPICIOUS_PATTERN) for column in columns)))
        .order_by(Athlete.provider_id.asc())
    ).all()
    repaired: list[RepairedAthleteName] = []
    for row in rows:
        for field in REPAIRABLE_NAME_FIELDS:
            value = getattr(row, field)
            if not value:
                continue
            fixed = repair_mojibake(value)
            if fixed == value:
                continue
            repaired.append(
                RepairedAthleteName(
                    athlete_id=row.id,
                    provider_id=row.provider_id,
                    field=field,
                    before=value,
                    after=fixed,
                )
            )
            if not dry_run:
                setattr(row, field, fixed)
    if repaired and not dry_run:
        session.flush()
    return repaired
